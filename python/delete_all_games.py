import subprocess

IMAGE_NAME = "sushi-go-test"


def reset_docker():
    print(f"--- Resetting {IMAGE_NAME} ---")

    # 1. Find the IDs of containers using this image
    # 'ancestor' filters by the image name
    get_ids_cmd = ["docker", "ps", "-a", "-q", "--filter", f"ancestor={IMAGE_NAME}"]
    container_ids = subprocess.check_output(get_ids_cmd).decode().split()

    if container_ids:
        print(f"Found {len(container_ids)} container(s). Removing...")
        # 2. Force remove the containers
        subprocess.run(["docker", "rm", "-f"] + container_ids)
    else:
        print("No existing containers found to remove.")

    # 3. Run the new container
    print(f"Starting new container from {IMAGE_NAME}...")
    run_cmd = [
        "docker", "run", "-d",
        "-p", "7878:7878",
        "-p", "8080:8080",
        IMAGE_NAME
    ]

    result = subprocess.run(run_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Success! New Container ID: {result.stdout[:12]}")
        print("Ports mapped: 7878 -> 7878 and 8080 -> 8080")
    else:
        print(f"Error starting container: {result.stderr}")


if __name__ == "__main__":
    reset_docker()