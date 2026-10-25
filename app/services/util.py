from fastapi import HTTPException

def raise_exception(code: int, msg : str):
    raise HTTPException(status_code=code, detail=msg)

def validate_none(obj, type : str):
    if obj is None:
        raise_exception(404, f"{type} not found")

def validate_exists(obj, type : str):
    if obj is not None:
        raise_exception(400, f"{type} already exists")
    