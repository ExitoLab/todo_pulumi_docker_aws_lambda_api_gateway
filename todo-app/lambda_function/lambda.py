import os
import logging
import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this as needed for your use case
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = 'DYNAMODB_TABLE'
table = dynamodb.Table(table_name)

@app.get("/todos")
async def get_todos():
    try:
        response = table.scan()
        return response.get('Items', [])
    except Exception as e:
        logging.error(f"Error getting todos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/todos", status_code=201)
async def create_todo(todo: dict):
    if not todo:
        raise HTTPException(status_code=400, detail="Invalid input")
    try:
        table.put_item(Item=todo)
        return todo
    except Exception as e:
        logging.error(f"Error creating todo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/todos/{id}")
async def update_todo(id: str, todo: dict):
    if 'text' not in todo:
        raise HTTPException(status_code=400, detail='Missing "text" in request body')
    try:
        table.update_item(
            Key={'id': id},
            UpdateExpression='SET #t = :t',
            ExpressionAttributeNames={'#t': 'text'},
            ExpressionAttributeValues={':t': todo['text']}
        )
        return todo
    except Exception as e:
        logging.error(f"Error updating todo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/todos/{id}", status_code=204)
async def delete_todo(id: str):
    try:
        table.delete_item(Key={'id': id})
        return {"detail": "Todo deleted"}  # You can return a message or an empty response
    except Exception as e:
        logging.error(f"Error deleting todo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    try:
        return {"message": "Everything looks good!"}
    except Exception as e:
        logging.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Define the Lambda handler function
def handler(event, context):
    """ Entry point for AWS Lambda """
    logging.info(f"Received event: {event}")
    mangum_handler = Mangum(app)
    return mangum_handler(event, context)