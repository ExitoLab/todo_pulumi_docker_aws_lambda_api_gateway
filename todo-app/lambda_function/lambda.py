import logging,os,uuid

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel
from typing import List, Dict, Optional

from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize FastAPI application
app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust the allowed origins for your use case
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("todo-dev")

class TodoItem(BaseModel):
    id: Optional[str]  # Make 'id' optional
    text: str
    completed: bool
    timestamp: Optional[int]  # Make 'timestamp' optional

@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    try:
        # Perform a scan operation on the DynamoDB table
        response = table.scan()
        # Return the 'Items' from the scan result
        items = response.get("Items", [])
        logging.debug(f"Fetched {len(items)} items from DynamoDB")
        return items
    except Exception as e:
        logging.error(f"Error getting todos: {e}")
        raise HTTPException(status_code=500, detail="Error fetching todos")

@app.post("/todos", status_code=201, response_model=TodoItem)
async def create_todo(todo: TodoItem):
    try:
        # Add the current timestamp to the todo item
        todo_dict = todo.dict()
        todo_dict["timestamp"] = int(datetime.utcnow().timestamp())  # Unix timestamp in seconds

        # Add the todo item to DynamoDB
        response = table.put_item(Item=todo_dict)
        logging.debug(f"DynamoDB put_item response: {response}")
        return todo_dict  # Return the updated item with the timestamp
    except boto3.exceptions.Boto3Error as boto_error:
        logging.error(f"Boto3Error: {boto_error}")
        raise HTTPException(status_code=500, detail=f"DynamoDB Error: {str(boto_error)}")
    except Exception as e:
        logging.error(f"Unexpected error creating todo: {e}")
        raise HTTPException(status_code=500, detail="Error creating todo")

@app.put("/todos/{id}", response_model=TodoItem)
async def update_todo(id: str, todo: Dict[str, str]):
    if "text" not in todo:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body")
    try:
        # Update the todo item in DynamoDB
        response = table.update_item(
            Key={"id": id},  # Ensure id is passed as a string
            UpdateExpression="SET #t = :t",
            ExpressionAttributeNames={"#t": "text"},
            ExpressionAttributeValues={":t": todo["text"]},
            ReturnValues="ALL_NEW"
        )
        updated_todo = response.get("Attributes")
        if not updated_todo:
            raise HTTPException(status_code=404, detail="Todo not found")
        logging.debug(f"Updated item: {updated_todo}")
        return updated_todo
    except Exception as e:
        logging.error(f"Error updating todo: {e}")
        raise HTTPException(status_code=500, detail="Error updating todo")

@app.delete("/todos/{id}", status_code=204)
async def delete_todo(id: str):
    try:
        # Delete the todo item from DynamoDB
        response = table.delete_item(Key={"id": id})  # Ensure id is passed as a string
        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status_code != 200:
            raise HTTPException(status_code=404, detail="Todo not found")
        logging.debug(f"Deleted item with id: {id}")
        return {"detail": "Todo deleted successfully"}
    except Exception as e:
        logging.error(f"Error deleting todo: {e}")
        raise HTTPException(status_code=500, detail="Error deleting todo")

@app.get("/health")
async def health():
    try:
        logging.debug("Health check initiated")
        # Simple check to see if everything is working
        return {"message": "Everything looks good!"}
    except Exception as e:
        logging.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail="Error performing health check")

# Define the Lambda handler function
def handler(event, context):
    logging.info(f"Received event: {event}")
    mangum_handler = Mangum(app)
    return mangum_handler(event, context)