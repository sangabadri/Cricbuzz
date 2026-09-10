from fastapi import HTTPException

def validate_none(obj, type : str):
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{type} not found")

def validate_exists(obj, type : str):
    if obj is not None:
        raise HTTPException(status_code=400, detail=f"{type} already exists")
    