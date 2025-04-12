"""
Test script to verify Redis connectivity.
Run with: python test_redis.py
"""
import os
import sys
import redis
import ssl

def test_redis_connection():
    """Test Redis connection with the configured URL."""
    # Get Redis URL from environment variables
    redis_url = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
    
    print(f"Testing Redis connection using URL: {redis_url}")
    
    # Check if SSL is needed
    use_ssl = redis_url.startswith('rediss://')
    
    try:
        # Configure Redis client
        if use_ssl:
            # For SSL connections
            r = redis.from_url(
                redis_url,
                ssl_cert_reqs=ssl.CERT_NONE
            )
        else:
            # For non-SSL connections
            r = redis.from_url(redis_url)
        
        # Test connection with ping
        ping_result = r.ping()
        print(f"Redis connection successful! Ping response: {ping_result}")
        
        # Simple key set/get test
        r.set('test_key', 'DentalScribe Redis Test')
        value = r.get('test_key')
        print(f"Redis set/get test: {value}")
        
        # Cleanup
        r.delete('test_key')
        
        return True
        
    except redis.ConnectionError as e:
        print(f"ERROR: Could not connect to Redis: {e}")
        print("\nPossible issues:")
        print("  1. Redis server is not running")
        print("  2. Redis URL is incorrect")
        print("  3. Network/firewall issues")
        print("  4. SSL configuration is incorrect (if using rediss://)")
        return False
        
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return False

def test_celery_config():
    """Test the Celery configuration."""
    try:
        from app.celery_config import broker_url, result_backend
        print(f"\nCelery Configuration:")
        print(f"  broker_url: {broker_url}")
        print(f"  result_backend: {result_backend}")
        
        # Test if broker_url is valid
        if broker_url.startswith(('redis://', 'rediss://')):
            print("  ✓ broker_url format is valid")
        else:
            print("  ✗ broker_url format appears invalid")
            
        # Test if result_backend is valid
        if result_backend.startswith(('redis://', 'rediss://')):
            print("  ✓ result_backend format is valid")
        else:
            print("  ✗ result_backend format appears invalid")
            
    except ImportError:
        print("\nERROR: Could not import Celery configuration. Make sure app/celery_config.py exists.")
    except Exception as e:
        print(f"\nERROR: An error occurred while testing Celery configuration: {e}")

if __name__ == "__main__":
    print("\n===== Redis Connectivity Test =====\n")
    
    # Test Redis connection
    connection_successful = test_redis_connection()
    
    # Test Celery configuration
    test_celery_config()
    
    # Summary
    print("\n===== Test Summary =====")
    if connection_successful:
        print("Redis connection: ✓ SUCCESS")
        print("\nYour Redis connection is working correctly!")
    else:
        print("Redis connection: ✗ FAILED")
        print("\nPlease check the error messages above and fix the Redis configuration.")
    
    print("\nNext steps:")
    if connection_successful:
        print("1. Try running Celery worker: 'celery -A app.celery_worker.celery worker --loglevel=info'")
        print("2. Test a simple task to ensure Celery tasks are being processed.")
    else:
        print("1. Make sure Redis is installed and running")
        print("2. Check your .env file for correct REDIS_URL or CELERY_BROKER_URL")
        print("3. For Heroku: Verify the Redis add-on is properly configured")