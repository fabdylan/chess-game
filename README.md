# Chess Royale

Un juego de ajedrez hecho con Python y Pygame, inspirado en una interfaz moderna.

## Caracteristicas

- Tablero grafico con piezas Unicode.
- Animacion al mover piezas.
- Resaltado de pieza seleccionada, ultimos movimientos y movimientos legales.
- Reglas principales del ajedrez: jaque, jaque mate, tablas por ahogado, enroque, en passant y promocion.
- Reloj de partida de 10 minutos por jugador.
- Historial de movimientos y panel de estado.
- Botones para reiniciar y cambiar la orientacion del tablero.

## Instalacion

1. Instala Python 3.11 o superior desde https://www.python.org/downloads/
2. Instala las dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecuta el juego:

```bash
python main.py
```

## Controles

- Click en una pieza propia para seleccionarla.
- Click en una casilla resaltada para mover.
- `R`: reiniciar partida.
- `F`: girar tablero.
- `Esc`: quitar seleccion.

## Cambiar el tiempo

En `main.py`, cambia esta linea:

```python
START_TIME_SECONDS = 10 * 60
```

Por ejemplo, para 5 minutos:

```python
START_TIME_SECONDS = 5 * 60
```

## Subir a GitHub

Cuando quieras publicarlo:

```bash
git init
git add .
git commit -m "Initial chess game"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/chess-royale.git
git push -u origin main
```

## Publicar en web con GitHub Pages

Este proyecto incluye un workflow de GitHub Actions en `.github/workflows/pygbag-pages.yml`.

Despues de subir los cambios a GitHub:

1. Entra a tu repositorio en GitHub.
2. Ve a `Settings > Pages`.
3. En `Build and deployment`, selecciona `GitHub Actions`.
4. Ve a la pestana `Actions`.
5. Abre `Build Pygbag Web Game` y ejecutalo si no corre automaticamente.

Cuando termine, GitHub te dara una URL parecida a:

```text
https://TU-USUARIO.github.io/NOMBRE-DEL-REPO/
```

Nota: para la web se usa `pygbag`. Si algun navegador no reproduce los sonidos MP3, convierte los sonidos a OGG y colocalos en `assets/sounds`.
