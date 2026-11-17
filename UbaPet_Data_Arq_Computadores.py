from machine import I2C, SPI, Pin
import framebuf
import os
import time


# --- Configuracion de sensores y periféricos ---
I2C_SCL = 22
I2C_SDA = 21
PIR_PIN = 32
IR_PIN = 33
VIB_PIN = 34

TFT_MOSI = 13
TFT_MISO = 36
TFT_SCK = 14
SPI_BAUDRATE = 20000000
TFT_CS = 12
TFT_DC = 27
TFT_RST = 26

# Pantalla tactil resistiva con controlador XPT2046, compartiendo SPI con el TFT.
TOUCH_CS = 25
TOUCH_SWAP_XY = True
TOUCH_INVERT_X = True
TOUCH_INVERT_Y = False
TOUCH_X_MIN = 250
TOUCH_X_MAX = 3850
TOUCH_Y_MIN = 250
TOUCH_Y_MAX = 3850
TOUCH_PRESSURE_MIN = 250

PIR_NIVEL_ACTIVO = 1
IR_NIVEL_ACTIVO = 1
VIB_NIVEL_ACTIVO = 0
PIR_CALENTAMIENTO_MS = 60000
VIBRACION_REGISTRO_INTERVALO_MS = 5000

# Hora local de Ubaté para inicializar el DS3231 si su oscilador se detuvo.
# Ajuste estos valores a la hora real antes de ejecutar por primera vez.
RTC_FECHA_HORA_INICIAL = (2026, 11, 17, 8, 24, 25)

COLOR_AGUAMARINA = 0x07EF
COLOR_FONDO = 0x0000
COLOR_NEGRO = 0x0000
COLOR_BLANCO = 0xFFFF
COLOR_GRIS = 0x2104
COLOR_ALERTA = 0xF800
COLOR_ACTIVO = 0x07E0
COLOR_MARRON = 0xC608

ANCHO_PANTALLA = 320
ALTO_PANTALLA = 240
CABECERA = 30
PIE = 220

i2c = None
spi = None
pin_pir = None
pin_ir = None
pin_vib = None
touch_cs = None
cs = None
dc = None
rst = None

movimiento_pendiente = 0
nombre_archivo_sesion = None
eventos_recientes = []
numero_eventos = 0
sesion_activa = True
modo_pantalla = "inicio"
mensaje_estado = ""
error_almacenamiento = False


# --- Driver TFT ILI9341 ---
def tft_cmd(cmd):
    dc.value(0)
    cs.value(0)
    spi.write(bytearray([cmd]))
    cs.value(1)


def tft_data(data):
    dc.value(1)
    cs.value(0)
    spi.write(data)
    cs.value(1)


def inicializar_pantalla():
    rst.value(0)
    time.sleep_ms(50)
    rst.value(1)
    time.sleep_ms(150)

    tft_cmd(0xCF)
    tft_data(bytearray([0x00, 0xC3, 0x30]))
    tft_cmd(0xED)
    tft_data(bytearray([0x64, 0x03, 0x12, 0x81]))
    tft_cmd(0xE8)
    tft_data(bytearray([0x85, 0x00, 0x78]))
    tft_cmd(0xCB)
    tft_data(bytearray([0x39, 0x2C, 0x00, 0x34, 0x02]))
    tft_cmd(0xF7)
    tft_data(bytearray([0x20]))
    tft_cmd(0xEA)
    tft_data(bytearray([0x00, 0x00]))
    tft_cmd(0x36)
    tft_data(bytearray([0xE8]))
    tft_cmd(0x3A)
    tft_data(bytearray([0x55]))
    tft_cmd(0x11)
    time.sleep_ms(120)
    tft_cmd(0x29)
    print("[UI] Pantalla lista.")


def dibujar_rectangulo(x, y, w, h, color):
    tft_cmd(0x2A)
    tft_data(bytearray([x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF]))
    tft_cmd(0x2B)
    tft_data(bytearray([y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF]))
    tft_cmd(0x2C)

    pixel = bytearray([color >> 8, color & 0xFF])
    chunk = bytearray(128)
    for index in range(0, len(chunk), 2):
        chunk[index] = pixel[0]
        chunk[index + 1] = pixel[1]

    total_pixels = w * h
    for _ in range(total_pixels // 64):
        tft_data(chunk)
    for _ in range(total_pixels % 64):
        tft_data(pixel)


def mostrar_texto_pequeno(x, y, texto, color_fondo, ancho=130):
    alto = 16
    buffer = bytearray(ancho * alto * 2)
    fbuf = framebuf.FrameBuffer(buffer, ancho, alto, framebuf.RGB565)
    fbuf.fill(color_fondo)
    fbuf.text(texto, 4, 4, COLOR_BLANCO)

    tft_cmd(0x2A)
    tft_data(bytearray([x >> 8, x & 0xFF, (x + ancho - 1) >> 8, (x + ancho - 1) & 0xFF]))
    tft_cmd(0x2B)
    tft_data(bytearray([y >> 8, y & 0xFF, (y + alto - 1) >> 8, (y + alto - 1) & 0xFF]))
    tft_cmd(0x2C)
    tft_data(buffer)


def dibujar_perrito(ox, oy):
    dibujar_rectangulo(ox + 2, oy + 12, 6, 8, COLOR_MARRON)
    dibujar_rectangulo(ox + 22, oy + 12, 6, 8, COLOR_MARRON)
    dibujar_rectangulo(ox + 6, oy + 16, 18, 12, COLOR_MARRON)
    dibujar_rectangulo(ox + 10, oy + 19, 2, 2, COLOR_NEGRO)
    dibujar_rectangulo(ox + 18, oy + 19, 2, 2, COLOR_NEGRO)
    dibujar_rectangulo(ox + 13, oy + 23, 4, 2, COLOR_NEGRO)
    dibujar_rectangulo(ox + 10, oy + 2, 3, 3, COLOR_ALERTA)
    dibujar_rectangulo(ox + 17, oy + 2, 3, 3, COLOR_ALERTA)
    dibujar_rectangulo(ox + 9, oy + 5, 12, 3, COLOR_ALERTA)
    dibujar_rectangulo(ox + 11, oy + 8, 8, 2, COLOR_ALERTA)
    dibujar_rectangulo(ox + 13, oy + 10, 4, 2, COLOR_ALERTA)
    dibujar_rectangulo(ox + 14, oy + 12, 2, 1, COLOR_ALERTA)


def dibujar_interfaz_estatica():
    dibujar_rectangulo(0, 0, ANCHO_PANTALLA, ALTO_PANTALLA, COLOR_FONDO)
    dibujar_rectangulo(0, 0, ANCHO_PANTALLA, CABECERA, COLOR_AGUAMARINA)
    dibujar_rectangulo(0, PIE, ANCHO_PANTALLA, ALTO_PANTALLA - PIE, COLOR_AGUAMARINA)
    dibujar_perrito(270, 2)


def dibujar_botones(izquierda, derecha):
    dibujar_rectangulo(0, PIE, ANCHO_PANTALLA, ALTO_PANTALLA - PIE, COLOR_AGUAMARINA)
    mostrar_texto_pequeno(5, 222, izquierda, COLOR_GRIS)
    mostrar_texto_pequeno(175, 222, derecha, COLOR_GRIS)


def actualizar_paneles(movimiento, perro_comiendo, agua_llena, hora_str, estado_pir):
    dibujar_rectangulo(0, CABECERA, ANCHO_PANTALLA, PIE - CABECERA, COLOR_FONDO)

    color_mov = COLOR_ACTIVO if movimiento else COLOR_GRIS
    dibujar_rectangulo(10, 38, 148, 85, color_mov)
    mostrar_texto_pequeno(18, 48, "MOVIMIENTO:", color_mov)
    mostrar_texto_pequeno(18, 75, estado_pir, color_mov)

    dibujar_rectangulo(162, 38, 148, 85, COLOR_GRIS)
    mostrar_texto_pequeno(170, 48, "UBAPET-DATA", COLOR_GRIS)
    mostrar_texto_pequeno(170, 75, hora_str, COLOR_GRIS)

    color_comida = COLOR_ACTIVO if perro_comiendo else COLOR_GRIS
    color_agua = COLOR_ACTIVO if agua_llena else COLOR_ALERTA
    dibujar_rectangulo(10, 128, 146, 86, color_comida)
    dibujar_rectangulo(164, 128, 146, 86, color_agua)
    mostrar_texto_pequeno(16, 140, "ACTIVIDAD", color_comida, 134)
    mostrar_texto_pequeno(
        16, 170, "PERRO COMIENDO" if perro_comiendo else "PERRO EN REPOSO",
        color_comida, 134
    )
    mostrar_texto_pequeno(170, 140, "ESTADO AGUA", color_agua, 134)
    mostrar_texto_pequeno(
        170, 170, "AGUA LLENA" if agua_llena else "CAMBIAR AGUA",
        color_agua, 134
    )
    if error_almacenamiento:
        mostrar_texto_pequeno(170, 190, "ERROR AL GUARDAR", COLOR_ALERTA, 134)


def actualizar_reloj(hora_str):
    mostrar_texto_pequeno(170, 75, hora_str, COLOR_GRIS)


def dibujar_registros():
    dibujar_rectangulo(0, CABECERA, ANCHO_PANTALLA, PIE - CABECERA, COLOR_FONDO)
    dibujar_rectangulo(10, 36, 300, 28, COLOR_GRIS)
    mostrar_texto_pequeno(20, 42, "EVENTOS DE ESTA SESION", COLOR_GRIS, 280)

    if not eventos_recientes:
        mostrar_texto_pequeno(20, 82, "SIN DETECCIONES", COLOR_FONDO, 280)
    else:
        for indice, evento in enumerate(eventos_recientes):
            mostrar_texto_pequeno(20, 70 + indice * 23, evento, COLOR_FONDO, 280)

    if nombre_archivo_sesion is None:
        detalle = "ESPERANDO HORA DEL RTC"
    else:
        detalle = "EVENTOS: " + str(numero_eventos)
    mostrar_texto_pequeno(20, 190, detalle, COLOR_FONDO, 280)


def dibujar_confirmacion():
    dibujar_rectangulo(0, CABECERA, ANCHO_PANTALLA, PIE - CABECERA, COLOR_FONDO)
    dibujar_rectangulo(10, 60, 300, 100, COLOR_ALERTA)
    mostrar_texto_pequeno(24, 80, "FINALIZAR Y GUARDAR", COLOR_ALERTA, 270)
    mostrar_texto_pequeno(24, 112, "REPORTE PARA EXCEL CSV", COLOR_ALERTA, 270)


def dibujar_sesion_finalizada():
    dibujar_rectangulo(0, CABECERA, ANCHO_PANTALLA, PIE - CABECERA, COLOR_FONDO)
    dibujar_rectangulo(10, 60, 300, 100, COLOR_GRIS)
    mostrar_texto_pequeno(24, 80, "SESION FINALIZADA", COLOR_GRIS, 270)
    if nombre_archivo_sesion is None:
        detalle = "NO HAY REPORTE"
    else:
        detalle = "CSV: " + str(numero_eventos) + " EVENTOS"
    mostrar_texto_pequeno(24, 112, detalle, COLOR_GRIS, 270)


# --- RTC DS3231 y almacenamiento CSV compatible con Excel ---
def bcd_a_dec(bcd):
    decenas = (bcd >> 4) & 0x0F
    unidades = bcd & 0x0F
    if decenas > 9 or unidades > 9:
        raise ValueError("El RTC contiene un valor BCD invalido")
    return decenas * 10 + unidades


def dec_a_bcd(valor):
    return ((valor // 10) << 4) | (valor % 10)


def dia_semana_ds3231(anio, mes, dia):
    if mes < 3:
        anio -= 1
        mes += 12
    siglo = anio // 100
    anio_siglo = anio % 100
    dia_semana = (
        dia + (13 * (mes + 1)) // 5 + anio_siglo
        + anio_siglo // 4 + siglo // 4 + 5 * siglo
    ) % 7
    return dia_semana if dia_semana else 7


def ajustar_reloj_ds3231(fecha_hora):
    if len(fecha_hora) != 6:
        raise ValueError("RTC_FECHA_HORA_INICIAL debe tener anio, mes, dia, hora, minuto y segundo")

    anio, mes, dia, hora, minuto, segundo = fecha_hora
    if anio < 2000 or anio > 2099 or mes < 1 or mes > 12:
        raise ValueError("La fecha inicial del DS3231 debe estar entre 2000 y 2099")
    dias_mes = (31, 29 if anio % 4 == 0 else 28, 31, 30, 31, 30,
                31, 31, 30, 31, 30, 31)
    if dia < 1 or dia > dias_mes[mes - 1]:
        raise ValueError("El dia de RTC_FECHA_HORA_INICIAL no es valido")
    if hora < 0 or hora > 23 or minuto < 0 or minuto > 59 or segundo < 0 or segundo > 59:
        raise ValueError("La hora de RTC_FECHA_HORA_INICIAL no es valida")

    registros = bytearray([
        dec_a_bcd(segundo),
        dec_a_bcd(minuto),
        dec_a_bcd(hora),
        dia_semana_ds3231(anio, mes, dia),
        dec_a_bcd(dia),
        dec_a_bcd(mes),
        dec_a_bcd(anio - 2000),
    ])
    i2c.writeto_mem(0x68, 0x00, registros)

    estado = i2c.readfrom_mem(0x68, 0x0F, 1)[0]
    i2c.writeto_mem(0x68, 0x0F, bytearray([estado & 0x7F]))
    if i2c.readfrom_mem(0x68, 0x0F, 1)[0] & 0x80:
        raise OSError("No se pudo borrar la bandera OSF del DS3231")

    fecha, hora_actual = obtener_tiempo_actual()
    print("[RTC] DS3231 ajustado: {} {}".format(fecha, hora_actual))
    return fecha, hora_actual


def obtener_tiempo_actual():
    datos = i2c.readfrom_mem(0x68, 0, 7)
    if i2c.readfrom_mem(0x68, 0x0F, 1)[0] & 0x80:
        raise ValueError("El DS3231 indica que su reloj se detuvo; ajuste la fecha y hora")
    segundo = bcd_a_dec(datos[0] & 0x7F)
    minuto = bcd_a_dec(datos[1] & 0x7F)

    registro_hora = datos[2]
    if registro_hora & 0x40:
        hora = bcd_a_dec(registro_hora & 0x1F)
        hora = (hora % 12) + (12 if registro_hora & 0x20 else 0)
    else:
        hora = bcd_a_dec(registro_hora & 0x3F)

    dia = bcd_a_dec(datos[4] & 0x3F)
    mes = bcd_a_dec(datos[5] & 0x1F)
    anio = 2000 + bcd_a_dec(datos[6]) + (100 if datos[5] & 0x80 else 0)

    if segundo > 59 or minuto > 59 or hora > 23 or mes < 1 or mes > 12:
        raise ValueError("El RTC DS3231 tiene una fecha u hora invalida")
    dias_mes = (31, 29 if anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if dia < 1 or dia > dias_mes[mes - 1]:
        raise ValueError("El RTC DS3231 tiene un dia invalido")

    return "{:04d}-{:02d}-{:02d}".format(anio, mes, dia), \
        "{:02d}:{:02d}:{:02d}".format(hora, minuto, segundo)


def inicializar_reloj():
    estado = i2c.readfrom_mem(0x68, 0x0F, 1)[0]
    if estado & 0x80:
        print("[RTC] El reloj se detuvo. Ajustando con RTC_FECHA_HORA_INICIAL.")
        return ajustar_reloj_ds3231(RTC_FECHA_HORA_INICIAL)
    return obtener_tiempo_actual()


def archivo_existe(nombre):
    try:
        os.stat(nombre)
        return True
    except OSError as error:
        if error.args and error.args[0] == 2:
            return False
        raise


def establecer_nombre_archivo(fecha, hora):
    global nombre_archivo_sesion
    base = "UbaPet_{}_{}".format(fecha.replace("-", ""), hora.replace(":", ""))
    nombre = base + ".csv"
    sufijo = 1
    while archivo_existe(nombre):
        nombre = "{}_{:02d}.csv".format(base, sufijo)
        sufijo += 1
    nombre_archivo_sesion = nombre


def guardar_registro(sensor, evento, movimiento, agua_llena, perro_comiendo,
                     fecha=None, hora=None):
    global error_almacenamiento, numero_eventos
    try:
        if fecha is None or hora is None:
            fecha, hora = obtener_tiempo_actual()
        if nombre_archivo_sesion is None:
            establecer_nombre_archivo(fecha, hora)

        nuevo = not archivo_existe(nombre_archivo_sesion)
        with open(nombre_archivo_sesion, "a") as archivo:
            if nuevo:
                archivo.write(
                    "Fecha;Hora;Sensor;Evento;PIR_Movimiento;IR_Objeto_Agua;"
                    "Vibracion_Comiendo;Agua_Llena;Estado_Agua\n"
                )
            archivo.write(
                "{};{};{};{};{};{};{};{};{}\n".format(
                    fecha,
                    hora,
                    sensor,
                    evento,
                    "DETECTADO" if movimiento else "SIN DETECCION",
                    "DETECTADO" if agua_llena else "SIN DETECCION",
                    "ACTIVO" if perro_comiendo else "INACTIVO",
                    "SI" if agua_llena else "NO",
                    "LLENA" if agua_llena else "CAMBIAR",
                )
            )
    except (OSError, ValueError) as error:
        error_almacenamiento = True
        print("[ERROR] No se pudo guardar el evento {}: {}".format(sensor, error))
        return False

    error_almacenamiento = False
    numero_eventos += 1
    etiqueta = "{} {}".format(hora[:5], sensor)
    eventos_recientes.append(etiqueta)
    if len(eventos_recientes) > 5:
        del eventos_recientes[0]
    print("[{}] Deteccion {} guardada en {}".format(hora, sensor, nombre_archivo_sesion))
    return True


def exportar_reporte_final():
    global error_almacenamiento, nombre_archivo_sesion
    try:
        fecha, hora = obtener_tiempo_actual()
        if nombre_archivo_sesion is None:
            establecer_nombre_archivo(fecha, hora)
        if not archivo_existe(nombre_archivo_sesion):
            with open(nombre_archivo_sesion, "w") as archivo:
                archivo.write(
                    "Fecha;Hora;Sensor;Evento;PIR_Movimiento;IR_Objeto_Agua;"
                    "Vibracion_Comiendo;Agua_Llena;Estado_Agua\n"
                )
    except (OSError, ValueError) as error:
        error_almacenamiento = True
        print("[ERROR] No se pudo finalizar el reporte CSV: {}".format(error))
        return False

    error_almacenamiento = False
    print("[CSV] Reporte final listo: {} ({} eventos)".format(
        nombre_archivo_sesion, numero_eventos
    ))
    return True


def nueva_sesion():
    global nombre_archivo_sesion, eventos_recientes, numero_eventos
    global sesion_activa, modo_pantalla, mensaje_estado, error_almacenamiento
    global movimiento_pendiente
    nombre_archivo_sesion = None
    eventos_recientes = []
    numero_eventos = 0
    movimiento_pendiente = 0
    if pin_pir is not None and pin_pir.value() == PIR_NIVEL_ACTIVO:
        movimiento_pendiente = 1
    sesion_activa = True
    modo_pantalla = "inicio"
    mensaje_estado = ""
    error_almacenamiento = False
    try:
        fecha, hora = inicializar_reloj()
        establecer_nombre_archivo(fecha, hora)
    except (OSError, ValueError) as error:
        mensaje_estado = "RTC SIN HORA"
        print("[ERROR] No se puede iniciar con hora del RTC: {}".format(error))


def finalizar_sesion():
    global sesion_activa, modo_pantalla, mensaje_estado
    if exportar_reporte_final():
        sesion_activa = False
        modo_pantalla = "finalizada"
        mensaje_estado = "CSV LISTO"


# --- Tactil XPT2046 ---
def leer_eje_tactil(comando):
    tx = bytearray([comando, 0, 0])
    rx = bytearray(3)
    touch_cs.value(0)
    try:
        spi.write_readinto(tx, rx)
    finally:
        touch_cs.value(1)
    return ((rx[1] << 8) | rx[2]) >> 3


def mapear_coordenada(valor, minimo, maximo, limite, invertir):
    if valor < minimo:
        valor = minimo
    elif valor > maximo:
        valor = maximo
    coordenada = (valor - minimo) * (limite - 1) // (maximo - minimo)
    return limite - 1 - coordenada if invertir else coordenada


def leer_tacto():
    spi.init(baudrate=2000000)
    try:
        raw_x = leer_eje_tactil(0xD0)
        raw_y = leer_eje_tactil(0x90)
        z1 = leer_eje_tactil(0xB0)
        z2 = leer_eje_tactil(0xC0)
    finally:
        spi.init(baudrate=SPI_BAUDRATE)

    presion = z1 + 4095 - z2
    if z1 == 0 or z2 >= 4095 or presion < TOUCH_PRESSURE_MIN:
        return None

    if TOUCH_SWAP_XY:
        valor_x, valor_y = raw_y, raw_x
    else:
        valor_x, valor_y = raw_x, raw_y

    x = mapear_coordenada(
        valor_x, TOUCH_X_MIN, TOUCH_X_MAX, ANCHO_PANTALLA, TOUCH_INVERT_X
    )
    y = mapear_coordenada(
        valor_y, TOUCH_Y_MIN, TOUCH_Y_MAX, ALTO_PANTALLA, TOUCH_INVERT_Y
    )
    return x, y


def procesar_tacto(x, y):
    global modo_pantalla, mensaje_estado, sesion_activa
    if y < PIE:
        return

    if modo_pantalla == "confirmar":
        if x < ANCHO_PANTALLA // 2:
            modo_pantalla = "inicio"
        else:
            finalizar_sesion()
        return

    if not sesion_activa:
        if x < ANCHO_PANTALLA // 2:
            nueva_sesion()
        else:
            modo_pantalla = "registros"
        return

    if modo_pantalla == "registros":
        if x < ANCHO_PANTALLA // 2:
            modo_pantalla = "inicio"
        else:
            modo_pantalla = "confirmar"
        return

    if x < ANCHO_PANTALLA // 2:
        modo_pantalla = "registros"
    else:
        modo_pantalla = "confirmar"


def actualizar_interfaz(movimiento, perro_comiendo, agua_llena, hora, estado_pir):
    if modo_pantalla == "registros":
        dibujar_registros()
        dibujar_botones("VOLVER", "FINALIZAR")
    elif modo_pantalla == "confirmar":
        dibujar_confirmacion()
        dibujar_botones("CANCELAR", "CONFIRMAR")
    elif modo_pantalla == "finalizada":
        dibujar_sesion_finalizada()
        dibujar_botones("NUEVA SESION", "REGISTROS")
    else:
        if not sesion_activa:
            estado_pir = "SESION CERRADA"
        actualizar_paneles(movimiento, perro_comiendo, agua_llena, hora, estado_pir)
        if sesion_activa:
            dibujar_botones("REGISTROS", "FINALIZAR")
        else:
            dibujar_botones("NUEVA SESION", "REGISTROS")


# La interrupcion solo marca una bandera; el guardado se hace fuera de la ISR.
def al_detectar_movimiento(pin):
    global movimiento_pendiente
    movimiento_pendiente = 1


def configurar_hardware():
    global i2c, spi, pin_pir, pin_ir, pin_vib, touch_cs, cs, dc, rst
    i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
    try:
        dispositivos = i2c.scan()
        print("[I2C] Dispositivos encontrados: {}".format(
            [hex(direccion) for direccion in dispositivos]
        ))
        if 0x68 not in dispositivos:
            print("[RTC] No se encontro DS3231 (0x68). Revise SDA=GPIO21, "
                  "SCL=GPIO22, alimentacion y GND.")
    except OSError as error:
        print("[I2C] No se pudo explorar el bus: {}".format(error))

    resistencia_pir = Pin.PULL_DOWN if PIR_NIVEL_ACTIVO else Pin.PULL_UP
    pin_pir = Pin(PIR_PIN, Pin.IN, resistencia_pir)
    pin_ir = Pin(IR_PIN, Pin.IN)
    pin_vib = Pin(VIB_PIN, Pin.IN)

    spi = SPI(
        1,
        baudrate=SPI_BAUDRATE,
        polarity=0,
        phase=0,
        mosi=Pin(TFT_MOSI),
        miso=Pin(TFT_MISO),
        sck=Pin(TFT_SCK),
    )
    cs = Pin(TFT_CS, Pin.OUT)
    dc = Pin(TFT_DC, Pin.OUT)
    rst = Pin(TFT_RST, Pin.OUT)
    touch_cs = Pin(TOUCH_CS, Pin.OUT)
    cs.value(1)
    touch_cs.value(1)


def main():
    global movimiento_pendiente, mensaje_estado
    configurar_hardware()
    inicializar_pantalla()
    dibujar_interfaz_estatica()
    nueva_sesion()

    print("--- UBAPET-DATA: MONITOREO ACTIVO ---")
    print("[PIR] Calentamiento de 60 segundos antes de habilitar interrupciones.")

    inicio = time.ticks_ms()
    pir_listo = False
    anterior_comiendo = False
    anterior_agua_llena = False
    movimiento = False
    movimiento_hasta = time.ticks_ms()
    perro_comiendo = pin_vib.value() == VIB_NIVEL_ACTIVO
    agua_llena = pin_ir.value() == IR_NIVEL_ACTIVO
    ultima_vibracion_registrada = time.ticks_add(
        time.ticks_ms(), -VIBRACION_REGISTRO_INTERVALO_MS
    )
    rtc_listo_anterior = None
    estado_interfaz_anterior = None
    hora_pantalla_anterior = None
    ultimo_tacto = time.ticks_ms()
    tacto_presionado = False

    while True:
        ahora = time.ticks_ms()
        if not pir_listo and time.ticks_diff(ahora, inicio) >= PIR_CALENTAMIENTO_MS:
            trigger = Pin.IRQ_RISING if PIR_NIVEL_ACTIVO else Pin.IRQ_FALLING
            pin_pir.irq(trigger=trigger, handler=al_detectar_movimiento)
            pir_listo = True
            if pin_pir.value() == PIR_NIVEL_ACTIVO:
                movimiento_pendiente = 1
            print("[PIR] Listo.")

        movimiento = pir_listo and pin_pir.value() == PIR_NIVEL_ACTIVO
        perro_comiendo = pin_vib.value() == VIB_NIVEL_ACTIVO
        agua_llena = pin_ir.value() == IR_NIVEL_ACTIVO

        try:
            fecha, hora = obtener_tiempo_actual()
            hora_pantalla = "{} {}".format(fecha[5:], hora)
            rtc_listo = True
        except (OSError, ValueError) as error:
            fecha = None
            hora = None
            hora_pantalla = "RTC SIN HORA"
            rtc_listo = False
            error_rtc = str(error)

        if rtc_listo != rtc_listo_anterior:
            if rtc_listo:
                print("[RTC] DS3231 disponible; se reanuda el registro con hora valida.")
                mensaje_estado = ""
            else:
                print("[ERROR] No se puede leer el DS3231: {}".format(error_rtc))
                print("[RTC] Revise SDA=GPIO21, SCL=GPIO22, VCC, GND y la direccion 0x68.")
                mensaje_estado = "RTC SIN HORA"
            rtc_listo_anterior = rtc_listo

        if sesion_activa and rtc_listo and pir_listo and movimiento_pendiente:
            if guardar_registro("MOVIMIENTO", "DETECTADO", True, agua_llena,
                                perro_comiendo, fecha, hora):
                movimiento_pendiente = 0
                movimiento_hasta = time.ticks_add(ahora, 3000)

        if sesion_activa and rtc_listo and perro_comiendo and not anterior_comiendo:
            if time.ticks_diff(ahora, ultima_vibracion_registrada) >= \
                    VIBRACION_REGISTRO_INTERVALO_MS:
                if guardar_registro("VIBRACION", "PERRO_COMIENDO", movimiento,
                                    agua_llena, True, fecha, hora):
                    ultima_vibracion_registrada = ahora

        if sesion_activa and rtc_listo and agua_llena and not anterior_agua_llena:
            guardar_registro("INFRARROJO", "AGUA_LLENA", movimiento,
                             True, perro_comiendo, fecha, hora)

        if rtc_listo:
            anterior_comiendo = perro_comiendo
            anterior_agua_llena = agua_llena

        if modo_pantalla == "inicio" and sesion_activa and not pir_listo:
            estado_pir = "CALENTANDO"
        elif modo_pantalla == "inicio" and sesion_activa:
            en_momento = movimiento or time.ticks_diff(movimiento_hasta, ahora) > 0
            estado_pir = "DETECTADO" if en_momento else "SIN MOVIMIENTO"
        else:
            estado_pir = "SESION CERRADA"
        movimiento_ui = movimiento or time.ticks_diff(movimiento_hasta, ahora) > 0

        estado_interfaz = (
            movimiento_ui,
            perro_comiendo,
            agua_llena,
            estado_pir,
            modo_pantalla,
            sesion_activa,
            numero_eventos,
            error_almacenamiento,
            mensaje_estado,
        )
        if estado_interfaz != estado_interfaz_anterior:
            estado_interfaz_anterior = estado_interfaz
            actualizar_interfaz(movimiento_ui, perro_comiendo, agua_llena,
                                hora_pantalla, estado_pir)

        if modo_pantalla == "inicio":
            if hora_pantalla != hora_pantalla_anterior:
                actualizar_reloj(hora_pantalla)
                hora_pantalla_anterior = hora_pantalla
        else:
            hora_pantalla_anterior = None

        tacto = leer_tacto()
        if tacto is None:
            tacto_presionado = False
        elif not tacto_presionado and time.ticks_diff(ahora, ultimo_tacto) >= 250:
            procesar_tacto(tacto[0], tacto[1])
            ultimo_tacto = ahora
            tacto_presionado = True
            estado_interfaz_anterior = None
            actualizar_interfaz(movimiento_ui, perro_comiendo, agua_llena,
                                hora_pantalla, estado_pir)

        time.sleep_ms(100)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[UI] Programa detenido desde Thonny.")
