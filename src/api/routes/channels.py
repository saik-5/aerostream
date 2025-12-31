"""
Channels Router
===============
Endpoints for sensor channel information.
"""

from typing import Optional
from fastapi import APIRouter, Query

from src.api.schemas import Channel, ChannelListResponse
from src.db.connection import execute_query


router = APIRouter()


@router.get("", response_model=ChannelListResponse)
async def list_channels(
    category: Optional[str] = None
):
    """List all sensor channels."""
    # Use actual column names from schema: name, display_name, unit
    query = """
        SELECT 
            channel_id, 
            name as channel_code, 
            display_name as channel_name,
            category, 
            unit as units, 
            sample_rate_hz
        FROM channels
        WHERE is_active = 1
    """
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    query += " ORDER BY channel_id"
    
    rows = execute_query(query, tuple(params))
    
    channels = [Channel(
        channel_id=row['channel_id'],
        channel_code=row['channel_code'],
        channel_name=row['channel_name'],
        category=row['category'],
        units=row['units'],
        sample_rate_hz=row['sample_rate_hz']
    ) for row in rows]
    
    return ChannelListResponse(channels=channels, total=len(channels))


@router.get("/categories")
async def list_categories():
    """List all channel categories."""
    query = """
        SELECT DISTINCT category, COUNT(*) as channel_count
        FROM channels
        WHERE is_active = 1
        GROUP BY category
        ORDER BY category
    """
    rows = execute_query(query, ())
    
    return {
        "categories": [
            {"name": row['category'], "channel_count": row['channel_count']}
            for row in rows
        ]
    }
