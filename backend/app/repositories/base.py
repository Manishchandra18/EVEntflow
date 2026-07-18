from bson import ObjectId
from fastapi import HTTPException, status


def object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return ObjectId(value)


def to_id(document: dict) -> dict:
    document["id"] = str(document.pop("_id"))
    return document
