from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from io import BytesIO
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
import icalendar

from core.db import get_db
from domain.repositories import get_repository
from services.orbit import OrbitPredictor
from domain.models import Satellite

router = APIRouter()

@router.get("/ics")
async def export_ics(
    norad_id: str = Query(..., description="NORAD ID of the satellite"),
    lat: float = Query(..., ge=-90, le=90, description="Observer latitude in degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Observer longitude in degrees"),
    elevation: float = Query(0.0, description="Observer elevation in meters"),
    mask: float = Query(10.0, description="Elevation mask in degrees"),
    days: int = Query(7, ge=1, le=30, description="Number of days to include"),
    db: Session = Depends(get_db)
):
    """
    Export upcoming satellite passes as an iCalendar (.ics) file.
    
    The calendar will include all passes within the specified number of days.
    """
    try:
        # Get satellite data
        satellite_repo = get_repository('satellite', db)
        satellite = satellite_repo.get_by_norad_id(norad_id)
        
        if not satellite:
            raise HTTPException(
                status_code=404,
                detail=f"Satellite with NORAD ID {norad_id} not found in database"
            )
        
        # Initialize orbit predictor
        predictor = OrbitPredictor(
            tle_line1=satellite.tle_line1,
            tle_line2=satellite.tle_line2,
            tle_epoch=satellite.tle_epoch
        )
        
        # Calculate time range
        start_time = datetime.utcnow().replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=days)
        
        # Find passes
        passes = []
        current_time = start_time
        
        while current_time < end_time:
            pass_data = predictor.find_next_pass(
                lat=lat,
                lon=lon,
                elevation=elevation,
                start_time=current_time,
                end_time=end_time,
                min_elevation=mask,
                time_step=60.0
            )
            
            if not pass_data:
                break
                
            passes.append(pass_data)
            current_time = pass_data['set_time'] + timedelta(minutes=5)
        
        # Create iCalendar
        cal = icalendar.Calendar()
        cal.add('prodid', '-//SatLink Planner//satlink-planner.com//')
        cal.add('version', '2.0')
        cal.add('name', f'Satellite Passes - NORAD {norad_id}')
        cal.add('x-wr-calname', f'Satellite Passes - NORAD {norad_id}')
        
        # Add pass events
        for idx, pass_data in enumerate(passes, 1):
            event = icalendar.Event()
            event.add('summary', f'Pass of {getattr(satellite, "name", f"SAT-{norad_id}")}')
            event.add('dtstart', pass_data['rise_time'].replace(tzinfo=timezone.utc))
            event.add('dtend', pass_data['set_time'].replace(tzinfo=timezone.utc))
            event.add('dtstamp', datetime.utcnow().replace(tzinfo=timezone.utc))
            
            # Add description with pass details
            duration_min = pass_data['duration_s'] / 60
            description = (
                f"Satellite: {getattr(satellite, 'name', f'SAT-{norad_id}')}\n"
                f"NORAD ID: {norad_id}\n"
                f"Max Elevation: {pass_data['max_elevation']:.1f}°\n"
                f"Duration: {duration_min:.1f} minutes\n"
                f"Rise: {pass_data['rise_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Set: {pass_data['set_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            event.add('description', description)
            
            # Add location
            event.add('location', f'Lat: {lat:.4f}, Lon: {lon:.4f}')
            
            # Add UID for the event
            event.add('uid', f'satpass-{norad_id}-{idx}-{pass_data["rise_time"].timestamp()}')
            
            cal.add_component(event)
        
        # Generate the iCalendar file
        ics_content = cal.to_ical()
        
        return Response(
            content=ics_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": f"attachment; filename=satellite_passes_{norad_id}.ics"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating iCalendar: {str(e)}"
        )

class PDFExportRequest(BaseModel):
    """Request model for PDF export"""
    norad_id: str
    lat: float
    lon: float
    elevation: float = 0.0
    mask: float = 10.0
    band: str
    rain_rate_mmh: float = 0.0
    tx_power_dbm: float = 40.0
    tx_antenna_gain_dbi: float = 30.0
    rx_antenna_gain_dbi: Optional[float] = None
    system_noise_temp_k: Optional[float] = None
    bandwidth_mhz: float = 10.0
    start_time: datetime
    end_time: datetime
    step_s: int = 60

def _generate_elevation_chart(points: List[Dict], output_buffer: BytesIO):
    """Generate an elevation vs time chart"""
    import matplotlib.pyplot as plt
    
    times = [p['timestamp'] for p in points]
    elevations = [p['elevation_deg'] for p in points]
    
    plt.figure(figsize=(8, 4))
    plt.plot(times, elevations, 'b-')
    plt.fill_between(times, 0, elevations, color='blue', alpha=0.1)
    plt.title('Satellite Elevation vs Time')
    plt.xlabel('Time')
    plt.ylabel('Elevation (deg)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save to buffer
    plt.savefig(output_buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close()
    output_buffer.seek(0)
    return output_buffer

@router.post("/pdf")
async def export_pdf(
    export_data: PDFExportRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a PDF report of the satellite pass analysis.
    
    This endpoint will return a one-page PDF summary including:
    - Badge with frame/TLE info
    - Chart of elevation vs time
    - Link budget parameters and results
    """
    try:
        from io import BytesIO
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        import matplotlib.pyplot as plt
        
        # Get satellite data
        satellite_repo = get_repository('satellite', db)
        satellite = satellite_repo.get_by_norad_id(export_data.norad_id)
        
        if not satellite:
            raise HTTPException(
                status_code=404,
                detail=f"Satellite with NORAD ID {export_data.norad_id} not found in database"
            )
        
        # Initialize orbit predictor
        predictor = OrbitPredictor(
            tle_line1=satellite.tle_line1,
            tle_line2=satellite.tle_line2,
            tle_epoch=satellite.tle_epoch
        )
        
        # Generate time points for the chart
        time_points = []
        current_time = export_data.start_time
        while current_time <= export_data.end_time:
            time_points.append(current_time)
            current_time += timedelta(seconds=export_data.step_s)
        
        # Calculate elevation data
        points = []
        for t in time_points:
            try:
                az, el, rng = predictor.get_az_el_range(
                    time=t,
                    lat=export_data.lat,
                    lon=export_data.lon,
                    elevation=export_data.elevation
                )
                points.append({
                    'timestamp': t,
                    'elevation_deg': el,
                    'azimuth_deg': az,
                    'range_km': rng
                })
            except Exception:
                continue
        
        # Generate elevation chart
        chart_buffer = BytesIO()
        _generate_elevation_chart(points, chart_buffer)
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=72)
        
        styles = getSampleStyleSheet()
        elements = []
        
        # Add title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            alignment=1  # Center
        )
        elements.append(Paragraph(f"Satellite Pass Analysis - {getattr(satellite, 'name', f'NORAD {export_data.norad_id}')}", title_style))
        
        # Add satellite info
        elements.append(Paragraph("Satellite Information", styles['Heading2']))
        
        sat_info = [
            ["NORAD ID:", export_data.norad_id],
            ["Name:", getattr(satellite, 'name', 'N/A')],
            ["TLE Epoch:", satellite.tle_epoch.strftime('%Y-%m-%d %H:%M:%S UTC')],
            ["TLE Age:", f"{((datetime.utcnow().replace(tzinfo=timezone.utc) - satellite.tle_epoch).total_seconds() / 86400):.1f} days"],
            ["TLE Line 1:", satellite.tle_line1],
            ["TLE Line 2:", satellite.tle_line2],
        ]
        
        sat_table = Table(sat_info, colWidths=[2*inch, 4*inch])
        sat_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(sat_table)
        elements.append(Spacer(1, 12))
        
        # Add ground station info
        elements.append(Paragraph("Ground Station Information", styles['Heading2']))
        
        gs_info = [
            ["Latitude:", f"{export_data.lat:.6f}°"],
            ["Longitude:", f"{export_data.lon:.6f}°"],
            ["Elevation:", f"{export_data.elevation:.1f} m"],
            ["Elevation Mask:", f"{export_data.mask:.1f}°"],
        ]
        
        gs_table = Table(gs_info, colWidths=[2*inch, 4*inch])
        gs_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(gs_table)
        elements.append(Spacer(1, 12))
        
        # Add link budget parameters
        elements.append(Paragraph("Link Budget Parameters", styles['Heading2']))
        
        link_budget_info = [
            ["Parameter", "Value", "Units"],
            ["Frequency Band", export_data.band, ""],
            ["TX Power", f"{export_data.tx_power_dbm:.1f}", "dBm"],
            ["TX Antenna Gain", f"{export_data.tx_antenna_gain_dbi:.1f}", "dBi"],
            ["RX Antenna Gain", f"{export_data.rx_antenna_gain_dbi or 'N/A'}", "dBi"],
            ["System Noise Temp", f"{export_data.system_noise_temp_k or 'N/A'}", "K"],
            ["Bandwidth", f"{export_data.bandwidth_mhz}", "MHz"],
            ["Rain Rate", f"{export_data.rain_rate_mmh:.1f}", "mm/h"],
        ]
        
        lb_table = Table(link_budget_info, colWidths=[2*inch, 1.5*inch, 0.5*inch])
        lb_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ]))
        elements.append(lb_table)
        elements.append(Spacer(1, 12))
        
        # Add elevation chart
        elements.append(Paragraph("Elevation vs Time", styles['Heading2']))
        elements.append(Image(chart_buffer, width=6*inch, height=3*inch))
        elements.append(Spacer(1, 12))
        
        # Add analysis period
        elements.append(Paragraph("Analysis Period", styles['Heading3']))
        period_text = (
            f"From {export_data.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} to "
            f"{export_data.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')} "
            f"(step: {export_data.step_s} seconds)"
        )
        elements.append(Paragraph(period_text, styles['Normal']))
        
        # Add footer
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            f"Generated by SatLink Planner on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ParagraphStyle('Footer', parent=styles['Italic'], fontSize=8, textColor=colors.grey)
        ))
        
        # Build the PDF
        doc.build(elements)
        
        # Return the PDF file
        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=satlink_report_{export_data.norad_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Required PDF generation libraries not installed: {str(e)}. Install with: pip install reportlab matplotlib"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating PDF: {str(e)}"
        )
