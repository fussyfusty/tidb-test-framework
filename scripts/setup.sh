#!/bin/bash
# TiDB Test Framework - One-click Setup Script
# Supports both conda and regular Python environments
# Compatible with bash and zsh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 TiDB Test Framework Setup${NC}"
echo "================================"

# Detect environment type
ENV_TYPE="unknown"
if [ -n "$CONDA_PREFIX" ]; then
    echo -e "${GREEN}✅ Detected conda environment: $CONDA_PREFIX${NC}"
    ENV_TYPE="conda"
else
    if [ -n "$VIRTUAL_ENV" ]; then
        echo -e "${GREEN}✅ Detected virtualenv: $VIRTUAL_ENV${NC}"
        ENV_TYPE="venv"
    else
        echo -e "${YELLOW}⚠️  No virtual environment detected${NC}"
        echo -e "${BLUE}📝 It's recommended to use a virtual environment${NC}"
        
        printf "Create a virtual environment? (y/n): "
        read -r response
        echo
        if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
            python3 -m venv venv
            source venv/bin/activate
            echo -e "${GREEN}✅ Created and activated virtual environment${NC}"
            ENV_TYPE="venv"
        else
            echo -e "${YELLOW}⚠️  Continuing with system Python${NC}"
            ENV_TYPE="system"
        fi
    fi
fi

# Check Python version
echo -e "\n${BLUE}📋 Checking Python version...${NC}"
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python $PY_VERSION detected"

if python3 -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)"; then
    echo -e "${GREEN}✅ Python version OK${NC}"
else
    echo -e "${RED}❌ Python 3.8+ required, found $PY_VERSION${NC}"
    exit 1
fi

# Check and configure pip mirror
echo -e "\n${BLUE}📦 Checking pip configuration...${NC}"
if pip config get global.index-url | grep -q "freewheel"; then
    echo -e "${YELLOW}⚠️  Detected company internal PyPI mirror${NC}"
    echo -e "${BLUE}📝 Testing mirror accessibility...${NC}"
    
    # Test if the mirror is accessible
    MIRROR_URL=$(pip config get global.index-url)
    if curl --output /dev/null --silent --head --fail "$MIRROR_URL"; then
        echo -e "${GREEN}✅ Company mirror is accessible${NC}"
    else
        echo -e "${YELLOW}⚠️  Company mirror is not accessible${NC}"
        echo -e "${BLUE}📝 Switching to public PyPI mirror (Tsinghua)${NC}"
        pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
        pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
    fi
fi

# Upgrade pip
echo -e "\n${BLUE}📦 Upgrading pip...${NC}"
python -m pip install --upgrade pip

# Install dependencies (only missing ones)
echo -e "\n${BLUE}📦 Installing missing dependencies...${NC}"

# Create a temporary Python script to check and install missing packages
cat > check_and_install.py << 'CHKEOF'
#!/usr/bin/env python3
import sys
import subprocess
import pkg_resources

required_packages = [
    'PyYAML',
    'pymysql',
    'SQLAlchemy',
    'pandas',
    'pytest',
    'pytest-cov',
    'python-dotenv',
    'loguru',
    'tqdm',
    'faker',
    'prometheus-client',
]

print("Checking installed packages...")
missing_packages = []

for package in required_packages:
    try:
        pkg_resources.require(package)
        print(f"  ✅ {package} already installed")
    except pkg_resources.DistributionNotFound:
        print(f"  ⚠️  {package} not found")
        missing_packages.append(package)
    except pkg_resources.VersionConflict as e:
        print(f"  ⚠️  {package} version conflict: {e}")
        missing_packages.append(package)

if missing_packages:
    print(f"\n📦 Installing {len(missing_packages)} missing packages...")
    for package in missing_packages:
        print(f"  Installing {package}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"    ✅ {package} installed successfully")
        else:
            print(f"    ❌ Failed to install {package}")
            print(f"       Error: {result.stderr.strip()}")
else:
    print("\n✅ All required packages are already installed!")
CHKEOF

# Run the check and install script
python check_and_install.py

# Verify installation
echo -e "\n${BLUE}🔍 Verifying installation...${NC}"

cat > verify_install.py << 'PYEOF'
#!/usr/bin/env python3
import sys
import importlib.metadata
import subprocess

required_packages = [
    ('yaml', 'PyYAML'),
    ('pymysql', 'pymysql'),
    ('sqlalchemy', 'SQLAlchemy'),
    ('pandas', 'pandas'),
    ('pytest', 'pytest'),
    ('dotenv', 'python-dotenv'),
    ('loguru', 'loguru'),
    ('tqdm', 'tqdm'),
    ('faker', 'faker'),
    ('prometheus_client', 'prometheus-client'),
]

print("\n📦 Checking installed packages:")
print("-" * 50)

all_success = True
missing_packages = []

for module_name, package_name in required_packages:
    try:
        __import__(module_name)
        try:
            version = importlib.metadata.version(package_name)
            print(f"  ✅ {package_name:20} {version}")
        except importlib.metadata.PackageNotFoundError:
            print(f"  ✅ {package_name:20} installed (version unknown)")
    except ImportError:
        print(f"  ⚠️  {package_name:20} Not installed")
        missing_packages.append(package_name)
        all_success = False

print("-" * 50)

if missing_packages:
    print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
    print("💡 You can install them manually:")
    print(f"   pip install {' '.join(missing_packages)}")
    sys.exit(1)
else:
    print("\n✅ All required packages are installed!")

# Test TiDB connection (optional)
print("\n🔌 Testing TiDB connection...")
try:
    import pymysql
    conn = pymysql.connect(
        host='127.0.0.1',
        port=4000,
        user='root',
        connect_timeout=5
    )
    with conn.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        version = cursor.fetchone()[0]
        print(f"✅ Connected to TiDB: {version}")
    conn.close()
except ImportError:
    print("⚠️  pymysql not available, skipping connection test")
except Exception as e:
    print(f"⚠️  Could not connect to TiDB: {e}")
    print("   Make sure TiDB is running: tiup playground")
PYEOF

# Run verification
python verify_install.py

# Set up PYTHONPATH
echo -e "\n${BLUE}🔧 Setting up PYTHONPATH...${NC}"
PROJECT_DIR=$(pwd)

if [ "$ENV_TYPE" = "conda" ] && [ -n "$CONDA_PREFIX" ]; then
    mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
    cat > "$CONDA_PREFIX/etc/conda/activate.d/pythonpath.sh" << EOF
#!/bin/bash
export PYTHONPATH=\$PYTHONPATH:$PROJECT_DIR
EOF
    echo -e "${GREEN}✅ PYTHONPATH configured for conda${NC}"
    
elif [ "$ENV_TYPE" = "venv" ] && [ -n "$VIRTUAL_ENV" ]; then
    mkdir -p "$VIRTUAL_ENV/bin"
    echo "export PYTHONPATH=\$PYTHONPATH:$PROJECT_DIR" >> "$VIRTUAL_ENV/bin/activate"
    echo -e "${GREEN}✅ PYTHONPATH configured for virtualenv${NC}"
    
else
    echo -e "${YELLOW}📝 Please set PYTHONPATH manually:${NC}"
    echo "   export PYTHONPATH=\$PYTHONPATH:$PROJECT_DIR"
    echo "   echo 'export PYTHONPATH=\$PYTHONPATH:$PROJECT_DIR' >> ~/.zshrc"
fi

# Create test file
cat > test_framework.py << 'PYEOF'
#!/usr/bin/env python3
"""
Simple test for TiDB Test Framework
"""

from tidb_test.connector import TiDBConnection
from tidb_test.utils import setup_logger
import logging

def main():
    logger = setup_logger('tidb-test', logging.INFO)
    logger.info("Starting TiDB Test Framework")
    
    try:
        with TiDBConnection() as conn:
            result = conn.fetch_all("SELECT VERSION()")
            version = result[0][0]
            logger.info(f"Connected to TiDB: {version}")
            
            conn.execute("CREATE DATABASE IF NOT EXISTS test")
            conn.execute("USE test")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Test table created/verified")
            
            conn.execute("INSERT INTO users (name) VALUES ('test_user')")
            logger.info("Test data inserted")
            
            users = conn.fetch_all("SELECT * FROM users")
            logger.info(f"Found {len(users)} users")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1
    
    logger.info("All tests passed!")
    return 0

if __name__ == "__main__":
    exit(main())
PYEOF

chmod +x test_framework.py

# Final instructions
echo -e "\n${GREEN}✅ Setup complete!${NC}"
echo "================================"
echo -e "${BLUE}Next steps:${NC}"
echo "1. Make sure TiDB is running:"
echo "   tiup playground v8.5.0 --db.port 4001"
echo ""
echo "2. Test the framework:"
echo "   python test_framework.py"
echo ""
echo "3. If you need to reactivate the environment later:"

if [ "$ENV_TYPE" = "conda" ]; then
    echo "   conda activate ${CONDA_DEFAULT_ENV}"
elif [ "$ENV_TYPE" = "venv" ]; then
    echo "   source venv/bin/activate"
fi

echo ""