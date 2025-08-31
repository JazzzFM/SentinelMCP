#!/usr/bin/env python3
"""
Simple development server starter for SentinelMCP
This allows starting the server without all dependencies installed
"""

import sys
import uvicorn
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    print("🚀 Starting SentinelMCP Development Server...")
    print("📝 Note: Some features may not work without all dependencies installed")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")
    
    try:
        # Import here to catch import errors gracefully
        from app.main import app
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Try installing dependencies with: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()