# Chess Royale

Chess Royale ahora es una version web hecha con HTML, CSS y JavaScript, lista para abrirse en navegador y publicarse sin friccion en GitHub Pages.

## Caracteristicas

- Tablero visual con piezas PNG.
- Movimientos legales de ajedrez, incluyendo jaque, jaque mate, ahogado, enroque, en passant y promocion automatica a reina.
- Reloj de 10 minutos por jugador.
- Historial de movimientos.
- Capturas visibles.
- Sonidos personalizados.
- Botones para reiniciar y girar el tablero.

## Archivos principales

- `index.html`: estructura de la aplicacion.
- `styles.css`: interfaz y estilos responsivos.
- `app.js`: logica del juego y renderizado del tablero.

## Abrir localmente

Puedes abrir `index.html` directamente en el navegador.

## Publicar en GitHub Pages

El repositorio incluye el workflow `.github/workflows/pages-static.yml`.

Despues de subir cambios a GitHub:

1. Ve a `Settings > Pages`.
2. En `Build and deployment`, selecciona `GitHub Actions`.
3. Ve a `Actions` y espera el workflow `Deploy Static Site`.

La URL final se vera asi:

```text
https://TU-USUARIO.github.io/NOMBRE-DEL-REPO/
```
