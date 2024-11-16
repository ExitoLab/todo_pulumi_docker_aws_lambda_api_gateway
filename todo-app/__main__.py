import pulumi
import pulumi_aws as aws
from pulumi_docker import Image, DockerBuild
import pulumi_docker as docker

# Step 1: Create an ECR repository
docker_image = "289940214902.dkr.ecr.us-east-1.amazonaws.com/todo-app:v1.1"

# Create an IAM Role for the Lambda function
lambda_role = aws.iam.Role("lambdaExecutionRole",
    assume_role_policy="""{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": "sts:AssumeRole",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Effect": "Allow",
          "Sid": ""
        }
      ]
    }"""
)

# Attach the basic execution policy to the role
lambda_policy_attachment = aws.iam.RolePolicyAttachment("lambdaExecutionPolicy",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)

# Create a Lambda function using the Docker image
lambda_function = aws.lambda_.Function("my-serverless-function",
    name="my-serverless-function",
    role=lambda_role.arn,  # Make sure you have the correct IAM role
    package_type="Image",   # Specify that this is a Docker image
    image_uri=docker_image,  # Use the image name from the previous step
    memory_size=512,        # Example memory size
    timeout=30             # Example timeout in seconds
)

# Create an API Gateway REST API
api = aws.apigateway.RestApi("my-api",
    description="My serverless API")

# Create a catch-all resource for the API
proxy_resource = aws.apigateway.Resource("proxy-resource",
    rest_api=api.id,
    parent_id=api.root_resource_id,
    path_part="{proxy+}")

# Create a method for the proxy resource that allows any method
method = aws.apigateway.Method("proxy-method",
    rest_api=api.id,
    resource_id=proxy_resource.id,
    http_method="ANY",
    authorization="NONE")

# Integration of Lambda with API Gateway using AWS_PROXY
integration = aws.apigateway.Integration("proxy-integration",
    rest_api=api.id,
    resource_id=proxy_resource.id,
    http_method=method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=lambda_function.invoke_arn)  # Ensure lambda_function is defined


lambda_permission = aws.lambda_.Permission("api-gateway-lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="apigateway.amazonaws.com",
    source_arn=pulumi.Output.concat(api.execution_arn, "/*/*")
)


# Deployment of the API, explicitly depends on method and integration to avoid timing issues
deployment = aws.apigateway.Deployment("api-deployment",
    rest_api=api.id,
    stage_name="dev",
    opts=pulumi.ResourceOptions(
        depends_on=[method, integration, lambda_permission]  # Ensures these are created before deployment
    )
)

# Output the API Gateway stage URL
api_invoke_url = pulumi.Output.concat(
    "https://", api.id, ".execute-api.", "us-east-1", ".amazonaws.com/", deployment.stage_name
)

pulumi.export("api_invoke_url", api_invoke_url)


# # Output the invoke URL of the API
# pulumi.export("api_invoke_url", pulumi.Output.all(api.id, aws.config.region).apply(lambda values: f"https://{values[0]}.execute-api.{values[1]}.amazonaws.com/dev/{proxy_resource.path_part}"))

# #How does Pulumi stores statesfile