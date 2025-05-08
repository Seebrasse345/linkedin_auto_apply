# Environment Setup for LinkedIn Auto Apply Bot

## OpenAI API Key Setup

This application requires an OpenAI API key to be set as an environment variable for generating cover letters and answering application questions.

### Windows Environment Variable Setup

1. **Setting the environment variable temporarily (for current session only)**:
   
   Open a PowerShell window and run:
   ```powershell

   ```

2. **Setting the environment variable permanently (for future sessions)**:
   
   Run the following in PowerShell with administrator privileges:
   ```powershell

   ```

   Or through the Windows GUI:
   1. Search for "Environment Variables" in the Start menu
   2. Click "Edit the system environment variables"
   3. Click "Environment Variables..." button
   4. Under "User variables", click "New..."
   5. Set Variable name: `OPENAI_API_KEY`
   6. Set Variable value: `your-openai-api-key-goes-here`

   7. Click "OK" on all windows

### Security Note

* Never commit API keys to your git repository
* The `.gitignore` file has been updated to exclude `.env` files
* If running the application in a production environment, use a secure secret management solution
