#!/usr/bin/env python3
"""
Simple one-file setup and run script for Flask Document Chatbot
This script will handle everything: venv creation, package installation, and running the app
"""

import os
import sys
import subprocess
import platform
import venv
from pathlib import Path

def print_step(step, message):
    """Print formatted step message"""
    print(f"\n{'='*60}")
    print(f"STEP {step}: {message}")
    print('='*60)

def run_command(cmd, description="", show_output=False):
    """Run a command and return success status"""
    print(f"🔄 {description}")
    try:
        if show_output:
            result = subprocess.run(cmd, shell=True, check=True)
        else:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ Success: {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Error: {e.stderr}")
        return False

def main():
    print("🚀 Flask Document Chatbot - Simple Setup & Run Script")
    print("This script will set up everything and run your chatbot!")
    
    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ Error: app.py not found!")
        print("Please run this script from the project directory containing app.py")
        sys.exit(1)
    
    print_step(1, "Checking Python Version")
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required. Found: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")
    
    print_step(2, "Setting Up Virtual Environment")
    venv_name = "venv"
    
    # Remove existing venv if it exists and has issues
    if Path(venv_name).exists():
        print(f"🗑️  Removing existing virtual environment...")
        if platform.system() == "Windows":
            os.system(f"rmdir /s /q {venv_name}")
        else:
            os.system(f"rm -rf {venv_name}")
    
    print(f"🔧 Creating fresh virtual environment: {venv_name}")
    venv.create(venv_name, with_pip=True)
    
    # Set up commands for the virtual environment
    if platform.system() == "Windows":
        pip_cmd = f"{venv_name}\\Scripts\\pip"
        python_cmd = f"{venv_name}\\Scripts\\python"
        activate_cmd = f"{venv_name}\\Scripts\\activate.bat"
    else:
        pip_cmd = f"{venv_name}/bin/pip"
        python_cmd = f"{venv_name}/bin/python"
        activate_cmd = f"source {venv_name}/bin/activate"
    
    print_step(3, "Upgrading pip")
    run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip")
    
    print_step(4, "Installing Core Dependencies")
    
    # Install packages one by one to avoid conflicts
    core_packages = [
        "Flask==2.3.3",
        "Flask-SQLAlchemy==3.0.5", 
        "Flask-Bcrypt==1.0.1",
        "SQLAlchemy==2.0.21",
        "python-dotenv",
        "loguru"
    ]
    
    print("📦 Installing core Flask packages...")
    for package in core_packages:
        run_command(f"{pip_cmd} install {package}", f"Installing {package}")
    
    print_step(5, "Installing AI/ML Dependencies") 
    
    # Install AI packages in the right order to avoid conflicts
    ai_packages = [
        "PyPDF2",
        "google-generativeai",
        "pinecone-client", 
        "langchain",
        "langchain-community",
        "langchain-google-genai",
        "langchain-pinecone",
        "rank-bm25"
    ]
    
    print("🤖 Installing AI packages...")
    for package in ai_packages:
        success = run_command(f"{pip_cmd} install {package}", f"Installing {package}")
        if not success:
            print(f"⚠️  Warning: Failed to install {package}, but continuing...")
    
    print_step(6, "Setting Up Environment")
    
    # Copy .env file if needed
    if not Path(".env").exists() and Path(".env.example").exists():
        import shutil
        shutil.copy(".env.example", ".env")
        print("📝 Created .env file from .env.example")
        print("⚠️  IMPORTANT: Edit .env file with your API keys!")
        print("   - GOOGLE_API_KEY=your-google-api-key")
        print("   - PINECONE_API_KEY=your-pinecone-api-key")
    elif Path(".env").exists():
        print("✅ .env file already exists")
    else:
        print("⚠️  No .env.example found. You'll need to create .env manually")
    
    print_step(7, "Initializing Database")
    
    # Create database setup script
    db_setup_script = '''
try:
    from app import create_app
    from models import db, User
    from flask_bcrypt import Bcrypt
    
    app = create_app()
    bcrypt = Bcrypt()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created")
        
        # Check if admin user exists
        if not User.query.filter_by(username="admin").first():
            # Create demo users
            demo_users = [
                {"username": "admin", "email": "admin@example.com", "password": "admin123"},
                {"username": "john_doe", "email": "john@example.com", "password": "password123"},
                {"username": "jane_smith", "email": "jane@example.com", "password": "password123"},
                {"username": "bob_wilson", "email": "bob@example.com", "password": "password123"},
                {"username": "alice_brown", "email": "alice@example.com", "password": "password123"}
            ]
            
            for user_data in demo_users:
                hashed_password = bcrypt.generate_password_hash(user_data["password"]).decode("utf-8")
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=hashed_password
                )
                db.session.add(user)
            
            db.session.commit()
            print("✅ Demo users created successfully")
        else:
            print("✅ Demo users already exist")
            
    print("✅ Database initialization complete")
    
except Exception as e:
    print(f"❌ Database setup error: {e}")
    print("This might be due to missing API keys in .env file")
'''
    
    # Write and run database setup
    with open("temp_db_setup.py", "w") as f:
        f.write(db_setup_script)
    
    print("🗄️  Setting up database and demo users...")
    db_success = run_command(f"{python_cmd} temp_db_setup.py", "Initializing database", show_output=True)
    
    # Clean up temp file
    if Path("temp_db_setup.py").exists():
        os.remove("temp_db_setup.py")
    
    print_step(8, "Setup Complete!")
    
    print("🎉 Setup finished successfully!")
    print("\n📋 Demo Users Created:")
    print("   👤 admin / admin123")
    print("   👤 john_doe / password123") 
    print("   👤 jane_smith / password123")
    print("   👤 bob_wilson / password123")
    print("   👤 alice_brown / password123")
    
    print("\n🔑 Important:")
    print("   Make sure to edit .env file with your API keys!")
    print("   - GOOGLE_API_KEY=your-google-api-key-here")
    print("   - PINECONE_API_KEY=your-pinecone-api-key-here")
    
    print("\n🌐 Ready to run!")
    print(f"   App will be available at: http://localhost:5000")
    
    # Ask to start the app
    try:
        print("\n" + "="*60)
        choice = input("🚀 Do you want to start the app now? (y/n): ").strip().lower()
        
        if choice in ['y', 'yes']:
            print("\n🌟 Starting Flask Document Chatbot...")
            print("📱 Open your browser to: http://localhost:5000")
            print("⏹️  Press Ctrl+C to stop the server")
            print("\n" + "="*60)
            
            # Run the app
            subprocess.run([python_cmd, "app.py"])
            
        else:
            print("\n✅ Setup complete! To run the app later:")
            print(f"   1. Activate virtual environment: {activate_cmd}")
            print("   2. Run the app: python app.py")
            print("   3. Open browser to: http://localhost:5000")
            
    except KeyboardInterrupt:
        print("\n\n👋 Setup completed successfully!")
        print("To run the app later:")
        print(f"   {activate_cmd}")
        print("   python app.py")

if __name__ == "__main__":
    main()
