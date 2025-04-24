#number of applications analysis both succeed and failed

import os

path = os.path.join(os.path.dirname(__file__), 'data')

successful_applications = os.path.join(path, 'successful_applications.json')
failed_applications = os.path.join(path, 'failed_applications.json')

with open(successful_applications, 'r') as f:
    successful_applications = len(f.read())

with open(failed_applications, 'r') as f:
    failed_applications = len(f.read())

print(f"Successful applications: {successful_applications}")
print(f"Failed applications: {failed_applications}")