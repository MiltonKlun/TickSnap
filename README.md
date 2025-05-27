# TickSnap

TickSnap is a chatbot designed to automate the creation of installment purchase tickets for a small business. It provides a simple and agile way for authorized personnel to record payments, generate digital receipts, and maintain a master client ledger using Google Sheets as a no-cost database, easily accessible to the client.

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-orange.svg)
![Google Sheets API](https://img.shields.io/badge/Google%20Sheets%20API-v4-green.svg)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Table of Contents

1.  [Project Overview](#project-overview)
2.  [Features](#features)
3.  [Why This Project?](#why-this-project)
4.  [Technology Stack](#technology-stack)
5.  [Project Structure](#project-structure)
6.  [Setup and Deployment](#setup-and-deployment)
    *   [Prerequisites](#prerequisites)
    *   [Configuration](#configuration)
    *   [Local Development (Optional)](#local-development-optional)
    *   [Deployment to AWS Lambda](#deployment-to-aws-lambda)
7.  [Usage](#usage)
8.  [Future Enhancements](#future-enhancements)
9.  [Contributing](#contributing)
10. [License](#license)

## Project Overview

The core function of this bot is to streamline the process of recording customer installment payments. An authorized user (e.g., a collector or salesperson) interacts with the bot via Telegram. They provide the client's name and the number of installments being paid. The bot then queries a master Google Sheet to find matching client credits. If multiple credits exist for a client, the bot presents options. Once a specific credit is selected, the bot:

1.  Generates a digital payment ticket (as an image).
2.  Sends the ticket to the user via Telegram.
3.  Logs the payment details in a dedicated "Log" sheet within the Google Sheet.
4.  (Future improvement could be to update the master credit record directly, though current `sheet.py` only logs).

This provides a cost-effective solution for the client, leveraging free/low-cost tiers of Telegram and Google Sheets, while offering a user-friendly interface for their staff.

## Features

*   **Secure Access:** Only authorized Telegram user IDs can interact with the bot.
*   **Client Search:** Searches for clients in a Google Sheet master list.
*   **Multiple Credit Handling:** Allows selection if a client has multiple active credits.
*   **Dynamic Ticket Generation:** Creates PNG image tickets with payment details (date, client info, item, installments paid, total paid, collector, etc.).
*   **Google Sheets Integration:**
    *   Reads client and credit data from a master sheet.
    *   Logs new payments to a separate log sheet.
*   **Serverless Deployment:** Designed to run on AWS Lambda for scalability and cost-efficiency.
*   **User-Friendly Interface:** Simple command-based interaction through Telegram.

## Why This Project?

For many small businesses, dedicated CRM or PoS systems can be expensive or overly complex. This project aimed to:

*   **Reduce Costs:** Utilize Telegram (free messaging) and Google Sheets (free/low-cost online spreadsheet) as core components.
*   **Improve Efficiency:** Automate ticket generation and payment logging, reducing manual work and potential errors.
*   **Enhance Accessibility:** Allow payment recording from anywhere using a mobile device with Telegram.
*   **Maintain Data Control:** The business owner retains easy access and control over their client data via Google Sheets.

## Technology Stack

| Technology             | Version/Type      | Purpose                                                                 | Why Chosen?                                                                                                   | Alternatives Considered                                           |
| :--------------------- | :---------------- | :---------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------- |
| **Python**             | `>=3.10` (3.12 used) | Core programming language.                                                | Versatile, large ecosystem of libraries, strong community support.                                            | Node.js, Go                                                       |
| **python-telegram-bot**| `>=20.0`          | Interacting with the Telegram Bot API.                                  | Well-maintained, feature-rich, asynchronous support.                                                          | `telebot` (pyTelegramBotAPI)                                      |
| **AWS Lambda**         | Serverless        | Hosting and running the bot logic without managing servers.             | Pay-per-use, auto-scaling, event-driven architecture fits well with webhook-based Telegram updates.           | EC2, Heroku, Google Cloud Functions, Azure Functions              |
| **Google Sheets API**  | `v4`              | Reading from and writing to Google Sheets.                              | Free, easily accessible by non-technical users (client owner), sufficient for this project's data needs.    | PostgreSQL, MySQL, DynamoDB, Firebase Realtime DB/Firestore       |
| **gspread**            | `>=5.0.0`         | Python client library for Google Sheets API.                            | Simplifies interaction with the Google Sheets API.                                                            | Direct Google API Client Library                                  |
| **Pillow (PIL)**       | `>=9.0.0`         | Generating image-based payment tickets.                                 | Powerful image manipulation library, easy to use for drawing text and shapes.                                 | `reportlab` (PDFs), `matplotlib` (overkill), generating HTML/CSS  |
| **Google Auth Libs**   | Various           | Handling OAuth2 authentication for Google Sheets.                       | Standard Google libraries for secure service account authentication.                                        | -                                                                 |
| **Docker**             | -                 | Creating a consistent build environment for Lambda deployment package.  | Ensures Linux AMD64 compatibility for Lambda, manages dependencies effectively.                             | Manual packaging, SAM CLI `sam build`                             |

## Project Structure

.                                                                                                                             
├── lambda_function.py                                                    
├── main_logic.py                               
├── sheet.py                                                
├── config.py                                      
├── utils.py                                                      
├── requirements.txt                                                                    
├── bot-credentials.json.example                             
├── .gitignore                                                             
└── README.md 

*(Note: Actual font files like `arial.ttf` would have to be included here or in a `fonts/` subdirectory, if packaged with the Lambda.)*

## Setup and Deployment

### Prerequisites

*   Python 3.10+
*   A Telegram Bot:
    *   Create one by talking to `@BotFather` on Telegram.
    *   Note down the **Bot Token**.
*   Google Cloud Platform Project:
    *   Enable the "Google Sheets API" and "Google Drive API".
    *   Create a **Service Account**.
    *   Download the Service Account JSON key file.
    *   Note the **Service Account Email**.
*   Google Sheet:
    *   Create a new Google Sheet.
    *   Note the **Sheet ID** (from its URL: `.../d/SHEET_ID/edit...`).
    *   **Share** this sheet with the Service Account Email (giving it "Editor" permissions).
    *   Structure your sheet with two tabs (default names are fine, `sheet.py` uses `sheet1` by default for the master data and implies a second sheet for logs if needed, but the current `log_payment_and_update_credit` in `sheet.py` logs to `sheet1` based on `find_first_empty_log_row`. This needs careful setup as per `sheet.py` column definitions).
    *   (Note: The sheet is in Spanish due to client requirements. Adjust both the Google Sheet and the code to match your preferred language).
        *   **Master Data Sheet (`Sheet1` or as configured):**
            *   `M`: Nombre (First Name)
            *   `N`: Apellido (Last Name)
            *   `P`: Articulo (Item)
            *   `Q`: Codigo (Item Code)
            *   `R`: ID Articulo (Item ID)
            *   `S`: Comercio (Store Name)
            *   `T`: Direccion (Address)
            *   `U`: Total Credito (Total Credit Amount)
            *   `V`: Importe Cuota (Installment Amount)
            *   `W`: Total Cuotas (Total Installments)
            *   `X`: Cuotas Abonadas (Installments Paid)
            *   ... (other columns as needed by `sheet.py`)
        *   **Log Sheet (referenced by `find_first_empty_log_row` for remito, but `log_payment_and_update_credit` writes to first sheet):**
            *   `A`: Fecha (Date)
            *   `B`: Nombre (First Name)
            *   `C`: Apellido (Last Name)
            *   `D`: Articulo (Item)
            *   `E`: ID Articulo (Item ID)
            *   `F`: Comercio (Store)
            *   `G`: Direccion (Address)
            *   `H`: Importe (Amount)
            *   `I`: Cant. Cuotas (Installments Qty)
*   TrueType Font files (e.g., `arial.ttf`, `arialbd.ttf`) for ticket generation. If not using system fonts, these need to be downloaded and packaged with the Lambda.

### Configuration

The bot relies on environment variables for sensitive information and configuration.

1.  **Google Service Account JSON:**
    *   Rename your downloaded service account key file (e.g., to `google-service-account.json`). **DO NOT COMMIT THIS FILE.**
    *   You can either place this file alongside your Lambda code and set `GOOGLE_SERVICE_ACCOUNT_PATH` or, for better security in Lambda, store its *content* in an environment variable.

2.  **Environment Variables:**

    | Variable                      | Description                                                                 | Example Value                                         |
    | :---------------------------- | :-------------------------------------------------------------------------- | :---------------------------------------------------- |
    | `TELEGRAM_TOKEN`              | Your Telegram Bot Token.                                                    | `1234567890:ABCDEFGHIJKLMNopqrstuvwxyz123456789`      |
    | `SHEET_ID`                    | The ID of your Google Sheet.                                                | `1txmjkTf6M1sy2LnrYcyq_HIYJWMx3Zrhl3JJUPD0R6g`        |
    | `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to your Google Service Account JSON key file.                          | `google-service-account.json`                         |
    | `ALLOWED_USER_IDS`            | Comma-separated string of Telegram User IDs allowed to use the bot.         | `123456789,987654321`                                 |
    | `FONT_PATH`                   | Directory containing `.ttf` font files (e.g., `arial.ttf`, `arialbd.ttf`).  | `.` (current dir) or `fonts/` (if in a subfolder)   |
    | `LOG_LEVEL`                   | Logging level for the application (DEBUG, INFO, WARNING, ERROR, CRITICAL).  | `INFO`                                                |

    For local development, you can use a `.env` file (add `.env` to your `.gitignore`!) and a library like `python-dotenv` to load these. For AWS Lambda, these are set in the Lambda function's configuration.

### Local Development (Optional)

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```
2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install python-dotenv # If using .env for local dev
    ```
4.  **Set up your `.env` file** (create it in the project root):
    ```env
    TELEGRAM_TOKEN="your_telegram_token"
    SHEET_ID="your_sheet_id"
    GOOGLE_SERVICE_ACCOUNT_PATH="path/to/your/google-service-account.json"
    ALLOWED_USER_IDS="your_user_id1,your_user_id2"
    FONT_PATH="." # Or path to your fonts directory
    LOG_LEVEL="INFO"
    ```
5.  To run locally (requires code adjustments for polling, as `lambda_function.py` is webhook-based):
    You would typically create a `local_run.py` that initializes and runs the `python-telegram-bot` application in polling mode. The current `lambda_function.py` is designed for webhook invocation by AWS Lambda.

### Deployment to AWS Lambda

1.  **Package your application:**
    *   Ensure your `requirements.txt` is up to date.
    *   Install dependencies into a deployment directory:
        ```bash
        mkdir deployment_package
        pip install -r requirements.txt -t ./deployment_package/
        ```
    *   Copy your Python scripts (`lambda_function.py`, `main_logic.py`, `sheet.py`, `config.py`, `utils.py`) into the `deployment_package` directory.
    *   If you are including font files, copy them into `deployment_package` (or a subdirectory like `deployment_package/fonts/` and adjust `FONT_PATH` env var accordingly).
    *   **IMPORTANT:** If using `GOOGLE_SERVICE_ACCOUNT_PATH`, copy your `google-service-account.json` file into `deployment_package`. (Alternatively, use the content of the JSON in an env var for better security).
    *   Create a ZIP file from the contents of `deployment_package`:
        ```bash
        cd deployment_package
        zip -r ../lambda_package.zip .
        cd ..
        ```
    *   The Docker command you used is also a great way to build the package, ensuring Linux compatibility:
        ```bash
        docker run --platform linux/amd64 -v "${PWD}:/var/task" public.ecr.aws/sam/build-python3.12 /bin/sh -c "pip install -r /var/task/requirements.txt -t /var/task/lambda_deploy_pkg/; cp /var/task/*.py /var/task/lambda_deploy_pkg/; exit"
        # Then zip the contents of lambda_deploy_pkg
        ```

2.  **Create an AWS Lambda Function:**
    *   Go to the AWS Lambda console.
    *   Click "Create function".
    *   Choose "Author from scratch".
    *   **Function name:** e.g., `TelegramTicketBot`
    *   **Runtime:** Python 3.12 (or your chosen Python version)
    *   **Architecture:** `x86_64` or `arm64` (ensure your Docker build matches if using arm64)
    *   **Permissions:** Create a new role with basic Lambda permissions, or use an existing one. This role will *not* need Google API permissions; authentication is handled by the service account.
    *   Click "Create function".

3.  **Configure the Lambda Function:**
    *   **Code source:** Upload the `lambda_package.zip` file.
    *   **Runtime settings:**
        *   **Handler:** `lambda_function.lambda_handler` (filename.function_name)
    *   **Environment variables:** Add all the variables listed in the [Configuration](#configuration) section.
        *   For `GOOGLE_SERVICE_ACCOUNT_PATH`, if you included the JSON in your ZIP, the path would be e.g., `google-service-account.json`.
        *   Alternatively, create an environment variable (e.g., `GOOGLE_CREDENTIALS_JSON_CONTENT`) and paste the *entire content* of your service account JSON file as its value. Then, modify `config.py` to load credentials from this string. This is generally more secure for Lambda.
    *   **Basic settings:** Adjust Memory (e.g., 256MB-512MB) and Timeout (e.g., 15-30 seconds) as needed.
    *   **Trigger:** Add an API Gateway trigger.
        *   Choose "Create a new API".
        *   Type: HTTP API (simpler, cheaper) or REST API.
        *   Security: "Open" (Telegram validates via the secret token in the URL).
        *   Note the **API endpoint URL**.

4.  **Set Telegram Webhook:**
    You need to tell Telegram where to send updates. Open a browser or use `curl`:
    ```
    https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/setWebhook?url=<YOUR_API_GATEWAY_ENDPOINT_URL>
    ```
    Replace `<YOUR_TELEGRAM_TOKEN>` and `<YOUR_API_GATEWAY_ENDPOINT_URL>`.
    You should get a response like `{"ok":true,"result":true,"description":"Webhook was set"}`.

## Usage

Once deployed and configured:

1.  Open Telegram and find your bot.
2.  Send the `/start` command. The bot will greet you.
3.  To register a payment, send a message in the format:
    `FirstName LastName NumberOfInstallments`
    Example: `Juan Perez 3`
4.  If matching credits are found, the bot will present buttons for each item. Click the button for the item you want to process.
5.  The bot will generate and send a payment ticket image.

## Future Enhancements

*   **Update Master Sheet:** Directly update "Cuotas Abonadas" (Installments Paid) in the master client sheet instead of just logging.
*   **Error Reporting:** More granular error reporting to the user or an admin chat.
*   **Localization/Internationalization (i18n):** Support for multiple languages.
*   **PDF Tickets:** Option to generate PDF tickets instead of/in addition to images.
*   **Advanced Search:** More flexible client search (e.g., by ID, partial name).
*   **Data Validation:** Stricter input validation.
*   **Unit and Integration Tests:** Improve code quality and reliability.
*   **CI/CD Pipeline:** Automate testing and deployment (e.g., using GitHub Actions and AWS SAM/CDK).
*   **User Management:** A more robust system for managing allowed users, perhaps via a separate Google Sheet or database.

## Contributing

Contributions are welcome! If you have suggestions or want to improve the bot, please feel free to:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/YourFeature`).
6.  Open a Pull Request.

Please ensure your code follows PEP 8 guidelines and includes comments where necessary.

⭐ If you found this project helpful, feel free to give it a star or share it!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details (you'll need to create a LICENSE.md file with the MIT license text).
