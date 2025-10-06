This project aims to provide a collection of automated sign-in scripts for various online service platforms. Each Python script is designed to automatically perform user sign-in tasks for specific websites or services, helping users automatically obtain daily rewards, points, or other forms of benefits.

### Key Features

- **AnyRouterSigner (anyrouter.py)**: Handles automated sign-ins based on the AnyRouter service.
- **IkuuuSigner (ikuuu.py)**: Implements login and sign-in functionality for the Ikuuu service.
- **RainyunSigner (rainyun.py)**: Provides sign-in and points inquiry features for the Rainyun service.
- **Other Scripts (leaflow.py, nodeseek.py)**: Contains additional service sign-in logic, expanding the project's applicability.

### Installation

1. Clone the repository to your local machine:
   ```
   git clone https://gitee.com/Viper373/ql-tasks.git
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Usage

Each script has its own configuration and execution method. Please refer to the `main()` function and class initialization parameters within each script for appropriate setup. In most cases, you will need to provide necessary authentication details such as usernames, passwords, or API keys, and ensure a stable internet connection to complete the sign-in process.

### Notes

- Before use, ensure you have read and understood the terms of service of each respective platform, and use the scripts provided by this project legally and responsibly.
- Adjust script parameters according to the specific requirements of the target service.
- As website structures may change over time, it is recommended to check for updates regularly to ensure script effectiveness.

### Contributions

Pull Requests for improving existing code or adding support for new services are welcome. For any bug reports or feature requests, please submit them via the Issue tracking system.

### License

This project is licensed under the MIT License. For more details, please refer to the [MIT License](https://opensource.org/licenses/MIT).