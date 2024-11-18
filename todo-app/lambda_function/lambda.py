import logging
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel,Field
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize FastAPI application
app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("todo-dev")

class TodoItem(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))  # Generate a UUID if not provided
    text: str
    completed: bool
    timestamp: Optional[int] = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))  # Current Unix timestamp if not provided


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    try:
        response = table.scan()
        items = response.get("Items", [])
        logging.debug(f"Fetched {len(items)} items from DynamoDB")
        return items
    except ClientError as e:
        logging.error(f"DynamoDB ClientError: {e}")
        raise HTTPException(status_code=500, detail="Error fetching todos")
    except Exception as e:
        logging.error(f"Error getting todos: {e}")
        raise HTTPException(status_code=500, detail="Error fetching todos")

@app.post("/todos", status_code=201, response_model=TodoItem)
async def create_todo(todo: TodoItem):
    try:
        todo_dict = todo.dict()
        todo_dict["id"] = todo_dict.get("id") or str(uuid.uuid4())
        todo_dict["timestamp"] = int(datetime.utcnow().timestamp())

        response = table.put_item(Item=todo_dict)
        logging.debug(f"DynamoDB put_item response: {response}")
        return todo_dict
    except ClientError as boto_error:
        logging.error(f"ClientError: {boto_error}")
        raise HTTPException(status_code=500, detail="DynamoDB Error")
    except Exception as e:
        logging.error(f"Unexpected error creating todo: {e}")
        raise HTTPException(status_code=500, detail="Error creating todo")

@app.put("/todos/{id}", response_model=TodoItem)
async def update_todo(id: str, timestamp: int, todo: Dict[str, str]):
    if "text" not in todo:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body")
    
    try:
        # Perform the update with both id and timestamp
        response = table.update_item(
            Key={"id": id, "timestamp": timestamp},  # Using both partition key and sort key
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
    
    except ClientError as e:
        logging.error(f"ClientError updating todo: {e}")
        raise HTTPException(status_code=500, detail="Error updating todo")
    except Exception as e:
        logging.error(f"Error updating todo: {e}")
        raise HTTPException(status_code=500, detail="Error updating todo")


@app.delete("/todos/{id}", status_code=204)
async def delete_todo(id: str, timestamp: int):
    try:
        # Delete the todo item using both the id (partition key) and timestamp (sort key)
        response = table.delete_item(Key={"id": id, "timestamp": timestamp})

        # Check if the deletion was successful
        if response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 200:
            logging.warning(f"Delete operation failed for id {id}: {response}")
            raise HTTPException(status_code=404, detail="Todo not found")
        
        logging.debug(f"Deleted item with id: {id} and timestamp: {timestamp}")
        return {"detail": "Todo deleted successfully"}

    except ClientError as e:
        logging.error(f"ClientError deleting todo with id {id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting todo: {str(e)}")

    except Exception as e:
        logging.error(f"Unexpected error deleting todo with id {id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting todo")


@app.get("/health")
async def health():
    try:
        logging.debug("Health check initiated")
        return {"message": "Everything looks good!"}
    except Exception as e:
        logging.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail="Error performing health check")

# Define the Lambda handler function
def handler(event, context):
    logging.info(f"Received event: {event}")
    mangum_handler = Mangum(app)
    return mangum_handler(event, context)
