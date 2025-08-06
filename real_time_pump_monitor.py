import asyncio
import websockets
import json
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class PumpToken:
    """Represents a newly detected Pump.fun token"""
    mint: str
    name: str
    symbol: str
    creator: str
    created_at: int
    market_cap: float
    price_usd: float
    bonding_curve_complete: bool
    migrated_to_raydium: bool = False
    detection_method: str = ""

class RealTimePumpMonitor:
    """Real-time monitor for Pump.fun token creation and migration events"""
    
    def __init__(self):
        self.session = None
        self.websockets = {}
        self.callbacks: List[Callable] = []
        self.monitoring = False
        
        # API endpoints
        self.pumpportal_ws = "wss://pumpportal.fun/api/data"
        self.solana_ws = "wss://api.mainnet-beta.solana.com"
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_monitoring()
        if self.session:
            await self.session.close()
            
    def add_callback(self, callback: Callable):
        """Add callback function for new token detection"""
        self.callbacks.append(callback)
        
    async def start_monitoring(self):
        """Start real-time monitoring for new Pump.fun tokens"""
        logger.info("Starting real-time Pump.fun monitoring...")
        self.monitoring = True
        
        # Start multiple monitoring streams
        tasks = []
        
        # Method 1: PumpPortal WebSocket
        tasks.append(asyncio.create_task(self._monitor_pumpportal_stream()))
        
        # Method 2: Solana program logs for Pump.fun
        tasks.append(asyncio.create_task(self._monitor_solana_program_logs()))
        
        # Method 3: Raydium migration detection
        tasks.append(asyncio.create_task(self._monitor_raydium_migrations()))
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            
    async def stop_monitoring(self):
        """Stop all monitoring streams"""
        logger.info("Stopping Pump.fun monitoring...")
        self.monitoring = False
        
        # Close all WebSocket connections
        for ws_name, ws in self.websockets.items():
            try:
                if ws and not ws.closed:
                    await ws.close()
                    logger.info(f"Closed {ws_name} WebSocket")
            except Exception as e:
                logger.debug(f"Error closing {ws_name}: {e}")
                
        self.websockets.clear()
        
    async def _monitor_pumpportal_stream(self):
        """Monitor PumpPortal WebSocket for new token events"""
        try:
            logger.info("Connecting to PumpPortal WebSocket...")
            
            async with websockets.connect(self.pumpportal_ws) as websocket:
                self.websockets['pumpportal'] = websocket
                
                # Subscribe to new token events
                subscribe_msg = {
                    "method": "subscribeNewToken"
                }
                await websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to new token events")
                
                # Subscribe to token migrations
                migration_msg = {
                    "method": "subscribeMigration"
                }
                await websocket.send(json.dumps(migration_msg))
                logger.info("Subscribed to token migrations")
                
                while self.monitoring:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(message)
                        
                        await self._process_pumpportal_event(data)
                        
                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        await websocket.ping()
                        continue
                        
        except Exception as e:
            logger.error(f"PumpPortal WebSocket error: {e}")
            
    async def _monitor_solana_program_logs(self):
        """Monitor Solana program logs for Pump.fun token creation"""
        try:
            logger.info("Connecting to Solana WebSocket for program logs...")
            
            # Pump.fun program ID
            pump_program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
            
            # WebSocket subscription for program logs
            subscribe_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "logsSubscribe",
                "params": [
                    {"mentions": [pump_program_id]},
                    {"commitment": "confirmed"}
                ]
            }
            
            async with websockets.connect(self.solana_ws) as websocket:
                self.websockets['solana_logs'] = websocket
                
                await websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to Pump.fun program logs")
                
                while self.monitoring:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(message)
                        
                        await self._process_solana_log_event(data)
                        
                    except asyncio.TimeoutError:
                        continue
                        
        except Exception as e:
            logger.error(f"Solana WebSocket error: {e}")
            
    async def _monitor_raydium_migrations(self):
        """Monitor Raydium for tokens migrating from Pump.fun"""
        try:
            logger.info("Monitoring Raydium migrations...")
            
            # Raydium program ID for initialize2 instruction
            raydium_program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
            
            subscribe_msg = {
                "jsonrpc": "2.0", 
                "id": 2,
                "method": "logsSubscribe",
                "params": [
                    {"mentions": [raydium_program_id]},
                    {"commitment": "confirmed"}
                ]
            }
            
            async with websockets.connect(self.solana_ws) as websocket:
                self.websockets['raydium_logs'] = websocket
                
                await websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to Raydium migration logs")
                
                while self.monitoring:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(message)
                        
                        await self._process_raydium_migration_event(data)
                        
                    except asyncio.TimeoutError:
                        continue
                        
        except Exception as e:
            logger.error(f"Raydium WebSocket error: {e}")
            
    async def _process_pumpportal_event(self, data: Dict):
        """Process PumpPortal WebSocket events"""
        try:
            event_type = data.get('type', '')
            
            if event_type == 'tokenCreated':
                # New token created on Pump.fun
                token_data = data.get('data', {})
                
                pump_token = PumpToken(
                    mint=token_data.get('mint', ''),
                    name=token_data.get('name', ''),
                    symbol=token_data.get('symbol', ''),
                    creator=token_data.get('creator', ''),
                    created_at=int(time.time()),
                    market_cap=token_data.get('marketCap', 0),
                    price_usd=token_data.get('priceUsd', 0),
                    bonding_curve_complete=False,
                    detection_method='pumpportal_creation'
                )
                
                logger.info(f"New token detected: {pump_token.name} ({pump_token.symbol})")
                await self._notify_callbacks(pump_token)
                
            elif event_type == 'tokenMigrated':
                # Token migrated to Raydium
                token_data = data.get('data', {})
                
                pump_token = PumpToken(
                    mint=token_data.get('mint', ''),
                    name=token_data.get('name', ''),
                    symbol=token_data.get('symbol', ''),
                    creator=token_data.get('creator', ''),
                    created_at=int(time.time()),
                    market_cap=token_data.get('marketCap', 69000),  # Migration threshold
                    price_usd=token_data.get('priceUsd', 0),
                    bonding_curve_complete=True,
                    migrated_to_raydium=True,
                    detection_method='pumpportal_migration'
                )
                
                logger.info(f"Token migrated: {pump_token.name} ({pump_token.symbol})")
                await self._notify_callbacks(pump_token)
                
        except Exception as e:
            logger.debug(f"Error processing PumpPortal event: {e}")
            
    async def _process_solana_log_event(self, data: Dict):
        """Process Solana program log events"""
        try:
            result = data.get('params', {}).get('result', {})
            logs = result.get('value', {}).get('logs', [])
            signature = result.get('value', {}).get('signature', '')
            
            # Look for token creation patterns in logs
            for log in logs:
                if 'create' in log.lower() and 'token' in log.lower():
                    # Extract transaction details and create PumpToken
                    await self._analyze_creation_transaction(signature)
                    break
                    
        except Exception as e:
            logger.debug(f"Error processing Solana log: {e}")
            
    async def _process_raydium_migration_event(self, data: Dict):
        """Process Raydium migration events"""
        try:
            result = data.get('params', {}).get('result', {})
            logs = result.get('value', {}).get('logs', [])
            
            # Look for initialize2 instruction (migration pattern)
            for log in logs:
                if 'initialize2' in log.lower():
                    logger.info(f"Raydium migration detected: {log}")
                    # Further processing to extract token mint
                    break
                    
        except Exception as e:
            logger.debug(f"Error processing Raydium migration: {e}")
            
    async def _analyze_creation_transaction(self, signature: str):
        """Analyze transaction details to extract token information"""
        try:
            if not self.session:
                return
                
            # Get transaction details from Solana RPC
            rpc_url = "https://api.mainnet-beta.solana.com"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                ]
            }
            
            async with self.session.post(rpc_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    # Process transaction to extract token details
                    logger.debug(f"Transaction analyzed: {signature}")
                    
        except Exception as e:
            logger.debug(f"Error analyzing transaction {signature}: {e}")
            
    async def _notify_callbacks(self, pump_token: PumpToken):
        """Notify all registered callbacks of new token"""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(pump_token)
                else:
                    callback(pump_token)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                
    async def get_recent_tokens(self, limit: int = 10) -> List[PumpToken]:
        """Get recently detected tokens (fallback method)"""
        try:
            if not self.session:
                return []
                
            # Fetch from PumpPortal API as backup
            url = "https://pumpportal.fun/api/tokens/new"
            params = {"limit": limit}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for token_data in data[:limit]:
                        pump_token = PumpToken(
                            mint=token_data.get('mint', ''),
                            name=token_data.get('name', ''),
                            symbol=token_data.get('symbol', ''),
                            creator=token_data.get('creator', ''),
                            created_at=token_data.get('created_timestamp', int(time.time())),
                            market_cap=token_data.get('market_cap_usd', 0),
                            price_usd=token_data.get('price_usd', 0),
                            bonding_curve_complete=token_data.get('bonding_curve_complete', False),
                            detection_method='api_fallback'
                        )
                        tokens.append(pump_token)
                        
                    return tokens
                    
        except Exception as e:
            logger.debug(f"Error fetching recent tokens: {e}")
            
        return []

# Integration with existing pump_scanner.py
async def integrate_real_time_monitor():
    """Integration function for pump_scanner.py"""
    
    async def token_detected_callback(pump_token: PumpToken):
        """Callback for when new tokens are detected"""
        logger.info(f"Real-time token: {pump_token.name} (${pump_token.symbol})")
        logger.info(f"  Mint: {pump_token.mint}")
        logger.info(f"  Market Cap: ${pump_token.market_cap:,.0f}")
        logger.info(f"  Method: {pump_token.detection_method}")
        
        # Apply safety filtering here
        # Trigger VIP FETCH notifications
        # Add to candidate list
    
    async with RealTimePumpMonitor() as monitor:
        monitor.add_callback(token_detected_callback)
        
        # Start monitoring (this runs indefinitely)
        await monitor.start_monitoring()

if __name__ == "__main__":
    # Test the real-time monitor
    asyncio.run(integrate_real_time_monitor())