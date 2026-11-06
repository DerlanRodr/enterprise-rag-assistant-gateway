"""
Módulo Gateway de Mensageria e Webhooks Corporativos.
"""
from src.gateway.webhook_handler import MessageGatewayHandler, InboundMessage, OutboundMessage

__all__ = ["MessageGatewayHandler", "InboundMessage", "OutboundMessage"]
