# Configuración para envío de correos electrónicos
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Configuración SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_REMITENTE = "samaracosmetics21@gmail.com"
CONTRASENA_APP = "ynepanyjzmmxevyr"

def enviar_correo_asignacion(destinatario_email, destinatario_nombre, factura_data, usuario_asignador):
    """
    Envía correo de notificación cuando se asigna una factura a un usuario
    
    Args:
        destinatario_email (str): Email del usuario asignado
        destinatario_nombre (str): Nombre del usuario asignado
        factura_data (dict): Datos de la factura asignada
        usuario_asignador (str): Nombre del usuario que asignó la factura
    """
    try:
        # Crear mensaje
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_REMITENTE
        msg['To'] = destinatario_email
        msg['Subject'] = f"📋 Nueva Factura Asignada - ID: {factura_data['id']}"
        
        # Crear contenido HTML del correo
        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Nueva Factura Asignada</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f4f7fc;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 10px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    padding: 30px;
                }}
                .factura-info {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #007bff;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                    padding: 8px 0;
                    border-bottom: 1px solid #e9ecef;
                }}
                .info-row:last-child {{
                    border-bottom: none;
                }}
                .info-label {{
                    font-weight: bold;
                    color: #495057;
                }}
                .info-value {{
                    color: #212529;
                }}
                .action-button {{
                    display: inline-block;
                    background-color: #28a745;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                    font-weight: bold;
                }}
                .footer {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    color: #6c757d;
                    font-size: 14px;
                }}
                .highlight {{
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 15px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📋 Nueva Factura Asignada</h1>
                    <p>Hola {destinatario_nombre}, se te ha asignado una nueva factura para revisar</p>
                </div>
                
                <div class="content">
                    <div class="highlight">
                        <strong>⚠️ Acción Requerida:</strong> Tienes una nueva factura asignada que requiere tu revisión y aprobación.
                    </div>
                    
                    <h3>📄 Información de la Factura</h3>
                    <div class="factura-info">
                        <div class="info-row">
                            <span class="info-label">🆔 ID de Factura:</span>
                            <span class="info-value"><strong>{factura_data['id']}</strong></span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">🏢 NIT:</span>
                            <span class="info-value">{factura_data['nit']}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">🏷️ Nombre del Cliente:</span>
                            <span class="info-value">{factura_data['nombre']}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">📋 Número de Factura:</span>
                            <span class="info-value">{factura_data['numero_factura']}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">📅 Fecha:</span>
                            <span class="info-value">{factura_data['fecha_seleccionada']}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">📂 Clasificación:</span>
                            <span class="info-value">{factura_data['clasificacion']}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">👤 Asignado por:</span>
                            <span class="info-value">{usuario_asignador}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">⏰ Fecha de Asignación:</span>
                            <span class="info-value">{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</span>
                        </div>
                    </div>
                    
                    <h3>🎯 Próximos Pasos</h3>
                    <ol>
                        <li>Inicia sesión en el sistema</li>
                        <li>Ve a la sección "Mis Asignaciones"</li>
                        <li>Revisa la factura asignada</li>
                        <li>Aprueba o rechaza según corresponda</li>
                    </ol>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="#" class="action-button">🔗 Ir a Mis Asignaciones</a>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Sistema de Gestión Documental</strong></p>
                    <p>Este es un correo automático, por favor no responder.</p>
                    <p>Fecha de envío: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Crear contenido de texto plano como respaldo
        text_content = f"""
        NUEVA FACTURA ASIGNADA
        
        Hola {destinatario_nombre},
        
        Se te ha asignado una nueva factura para revisar:
        
        ID de Factura: {factura_data['id']}
        NIT: {factura_data['nit']}
        Cliente: {factura_data['nombre']}
        Número de Factura: {factura_data['numero_factura']}
        Fecha: {factura_data['fecha_seleccionada']}
        Clasificación: {factura_data['clasificacion']}
        Asignado por: {usuario_asignador}
        Fecha de Asignación: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        Próximos pasos:
        1. Inicia sesión en el sistema
        2. Ve a "Mis Asignaciones"
        3. Revisa y aprueba la factura
        
        Sistema de Gestión Documental
        """
        
        # Adjuntar contenido
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # Enviar correo
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_REMITENTE, CONTRASENA_APP)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Correo enviado exitosamente a {destinatario_email}")
        return True
        
    except Exception as e:
        print(f"❌ Error enviando correo a {destinatario_email}: {e}")
        return False
