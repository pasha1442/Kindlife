# from fastapi import FastAPI, HTTPException, Header
# from typing import Optional
# from pydantic import BaseModel
# from server_connection import hit_query 

# app = FastAPI()

# class QueryRequest(BaseModel):
#     query: str

# VALID_API_KEY = "auriga123"

# @app.post("/execute-query")
# async def run_query(
#     request: QueryRequest,
#     api_key: Optional[str] = Header(None)
# ):
#     if api_key != VALID_API_KEY:
#         raise HTTPException(status_code=401, detail="Invalid API key")
    
#     try:
#         result = hit_query(request.query)
#         return {
#             "success": True,
#             "data": result
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

from fastapi import FastAPI, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
from server_connection import hit_query 

app = FastAPI()

class QueryRequest(BaseModel):
    query: str

VALID_API_KEY = "auriga123"

@app.post("/execute-query/")
async def run_query(
    request: QueryRequest,
    api_key: Optional[str] = Header(None, alias="api-key")
):
    print(f"Received API key: {api_key}")  # Debugging line
    if api_key != VALID_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        result = hit_query(request.query)
        if not result:
            raise HTTPException(status_code=404, detail="No data found")
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
