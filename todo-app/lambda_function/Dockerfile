# Stage 1: Build dependencies on Ubuntu
FROM ubuntu:22.04 as builder

WORKDIR /app

# Install Python and pip
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies into a local directory
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt -t /app/python

# Stage 2: Lambda-compatible final image
FROM public.ecr.aws/lambda/python:3.10

# Copy dependencies from the builder stage
COPY --from=builder /app/python ${LAMBDA_TASK_ROOT}

# Copy Lambda function code
COPY lambda.py ${LAMBDA_TASK_ROOT}/lambda.py

# Set the Lambda handler
CMD ["lambda.handler"]
