"""
Retry Queue Mechanism for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import asyncio
import logging
from typing import Callable, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from datetime import datetime
import json


logger = logging.getLogger(__name__)


class RetryQueue:
    """Queue and retry mechanism for handling failures with exponential backoff"""
    
    def __init__(self, max_attempts: int = 3, base_delay: int = 5):
        """Initialize retry queue with configuration"""
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.queue = asyncio.Queue()
        self.is_running = False
        self.failed_operations = []
        
    async def start(self):
        """Start the retry queue processor"""
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self._process_queue())
            logger.info("🔄 Retry queue started")
    
    async def stop(self):
        """Stop the retry queue processor"""
        self.is_running = False
        logger.info("⏸️  Retry queue stopped")
    
    async def add_operation(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ):
        """Add an operation to the retry queue"""
        operation_data = {
            'operation': operation,
            'name': operation_name,
            'args': args,
            'kwargs': kwargs,
            'attempts': 0,
            'timestamp': datetime.now().isoformat()
        }
        await self.queue.put(operation_data)
        logger.info(f"📥 Operation '{operation_name}' added to retry queue")
    
    async def _process_queue(self):
        """Process operations from the retry queue"""
        while self.is_running:
            try:
                operation_data = await asyncio.wait_for(
                    self.queue.get(), 
                    timeout=1.0
                )
                await self._execute_with_retry(operation_data)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Error processing queue: {e}", exc_info=True)
    
    async def _execute_with_retry(self, operation_data: dict):
        """Execute operation with retry logic using exponential backoff"""
        operation = operation_data['operation']
        name = operation_data['name']
        args = operation_data['args']
        kwargs = operation_data['kwargs']
        
        operation_data['attempts'] += 1
        attempt = operation_data['attempts']
        
        try:
            logger.info(f"🔄 Attempt {attempt}/{self.max_attempts} for '{name}'")
            
            # Execute the operation
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            
            logger.info(f"✅ Operation '{name}' succeeded on attempt {attempt}")
            return result
            
        except Exception as e:
            logger.warning(f"⚠️  Operation '{name}' failed on attempt {attempt}: {e}")
            
            if attempt < self.max_attempts:
                # Calculate exponential backoff delay
                delay = self.base_delay * (2 ** (attempt - 1))
                logger.info(f"⏳ Retrying '{name}' in {delay} seconds...")
                await asyncio.sleep(delay)
                
                # Re-queue for retry
                await self.queue.put(operation_data)
            else:
                # Max attempts reached, log as failed
                logger.error(f"❌ Operation '{name}' failed after {self.max_attempts} attempts")
                self.failed_operations.append({
                    **operation_data,
                    'error': str(e),
                    'failed_at': datetime.now().isoformat()
                })
    
    def get_failed_operations(self) -> list:
        """Get list of failed operations"""
        return self.failed_operations
    
    def clear_failed_operations(self):
        """Clear the failed operations list"""
        self.failed_operations.clear()
        logger.info("🧹 Failed operations cleared")


def with_retry(
    max_attempts: int = 3,
    base_delay: int = 5,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for adding retry logic to functions with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        exceptions: Tuple of exception types to retry on
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=base_delay, max=60),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=base_delay, max=60),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator