import pulumi, json
import pulumi_aws as aws
from pulumi_docker import Image, DockerBuild
import pulumi_docker as docker

from pulumi import Config

# Create a config object to access configuration values
config = pulumi.Config()

docker_image = config.get("docker_image")
environment = config.get("environment")
region = config.get("region")

aws.config.region = region

# First, create the DynamoDB table with just `id` as the primary key
dynamodb_table = aws.dynamodb.Table(
    f"todo-{environment}",
    name=f"todo-{environment}",
    hash_key="id",  # Only `id` as the partition key
    attributes=[
        aws.dynamodb.TableAttributeArgs(
            name="id",
            type="S"  # `S` for string type (use appropriate type for `id`)
        ),
    ],
    billing_mode="PAY_PER_REQUEST",  # On-demand billing mode
    tags={
        "Environment": environment,
        "Created_By": "Pulumi"
    }
)

# Create an IAM Role for the Lambda function
# Create Lambda execution role
lambda_role = aws.iam.Role(
    "lambdaExecutionRole",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }]
    })
)

# Create inline policy for the role
dynamodb_policy = aws.iam.RolePolicy(
    f"lambdaRolePolicy-{environment}",
    role=lambda_role.id,
    policy=pulumi.Output.json_dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:Scan",
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query"
                ],
                "Resource": [
                    dynamodb_table.arn,
                    pulumi.Output.concat(dynamodb_table.arn, "/*")
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            }
        ]
    })
)

# Create a Lambda function using the Docker image
lambda_function = aws.lambda_.Function(
    f"my-serverless-function-{environment}",
    role=lambda_role.arn,
    package_type="Image",
    image_uri=docker_image,
    memory_size=512,
    timeout=30,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role])
)

# Create an API Gateway REST API
api = aws.apigateway.RestApi(f"my-api-{environment}",
    description="My serverless API")

# Create a catch-all resource for the API
proxy_resource = aws.apigateway.Resource(f"proxy-resource-{environment}",
    rest_api=api.id,
    parent_id=api.root_resource_id,
    path_part="{proxy+}")

# Create a method for the proxy resource that allows any method
method = aws.apigateway.Method(f"proxy-method-{environment}",
    rest_api=api.id,
    resource_id=proxy_resource.id,
    http_method="ANY",
    authorization="NONE")

# Integration of Lambda with API Gateway using AWS_PROXY
integration = aws.apigateway.Integration(f"proxy-integration-{environment}",
    rest_api=api.id,
    resource_id=proxy_resource.id,
    http_method=method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=lambda_function.invoke_arn)  # Ensure lambda_function is defined

lambda_permission = aws.lambda_.Permission(f"api-gateway-lambda-permission-{environment}",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="apigateway.amazonaws.com",
    source_arn=pulumi.Output.concat(api.execution_arn, "/*/*")
)

# Deployment of the API, explicitly depends on method and integration to avoid timing issues
deployment = aws.apigateway.Deployment(f"api-deployment-{environment}",
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

# #How does Pulumi stores statesfile