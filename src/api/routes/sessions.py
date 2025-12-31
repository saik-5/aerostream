"""
Sessions Router
===============
Endpoints for test session management.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import Session, SessionListResponse
from src.db.connection import execute_query


router = APIRouter()


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    model_id: Optional[int] = None,
    cell_id: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100)
):
    """List all test sessions."""
    # Use actual column names from schema
    query = """
        SELECT 
            s.session_id, s.session_name, 
            s.model_id, m.model_name,
            s.cell_id as test_cell_id, tc.cell_name as test_cell_name,
            s.created_at as ts_start, NULL as ts_end, s.notes,
            (SELECT COUNT(*) FROM runs r WHERE r.session_id = s.session_id) as run_count
        FROM test_sessions s
        LEFT JOIN models m ON s.model_id = m.model_id
        LEFT JOIN test_cells tc ON s.cell_id = tc.cell_id
        WHERE 1=1
    """
    params = []
    
    if model_id:
        query += " AND s.model_id = ?"
        params.append(model_id)
    
    if cell_id:
        query += " AND s.cell_id = ?"
        params.append(cell_id)
    
    # Get total count
    count_query = f"""
        SELECT COUNT(*) as total
        FROM test_sessions s
        WHERE 1=1
        {'AND s.model_id = ?' if model_id else ''}
        {'AND s.cell_id = ?' if cell_id else ''}
    """
    count_params = []
    if model_id:
        count_params.append(model_id)
    if cell_id:
        count_params.append(cell_id)
    
    count_result = execute_query(count_query, tuple(count_params))
    total = count_result[0]['total'] if count_result else 0
    
    # Add pagination
    offset = (page - 1) * page_size
    query += f" ORDER BY s.session_id DESC OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"
    
    rows = execute_query(query, tuple(params))
    
    sessions = [Session(
        session_id=row['session_id'],
        session_name=row['session_name'],
        model_id=row['model_id'],
        model_name=row['model_name'],
        test_cell_id=row['test_cell_id'],
        test_cell_name=row['test_cell_name'],
        ts_start=row['ts_start'],
        ts_end=row['ts_end'],
        run_count=row['run_count'] or 0,
        notes=row['notes']
    ) for row in rows]
    
    return SessionListResponse(sessions=sessions, total=total)


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: int):
    """Get details for a specific session."""
    query = """
        SELECT 
            s.session_id, s.session_name, 
            s.model_id, m.model_name,
            s.cell_id as test_cell_id, tc.cell_name as test_cell_name,
            s.created_at as ts_start, NULL as ts_end, s.notes,
            (SELECT COUNT(*) FROM runs r WHERE r.session_id = s.session_id) as run_count
        FROM test_sessions s
        LEFT JOIN models m ON s.model_id = m.model_id
        LEFT JOIN test_cells tc ON s.cell_id = tc.cell_id
        WHERE s.session_id = ?
    """
    rows = execute_query(query, (session_id,))
    
    if not rows:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    row = rows[0]
    return Session(
        session_id=row['session_id'],
        session_name=row['session_name'],
        model_id=row['model_id'],
        model_name=row['model_name'],
        test_cell_id=row['test_cell_id'],
        test_cell_name=row['test_cell_name'],
        ts_start=row['ts_start'],
        ts_end=row['ts_end'],
        run_count=row['run_count'] or 0,
        notes=row['notes']
    )
