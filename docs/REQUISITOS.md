# Requisitos

La columna **Desde** indica en qué versión quedó cumplido cada requisito.

## Requisitos funcionales

| ID | Requisito | Desde |
|---|---|---|
| RF-01 | Dos jugadores pueden jugar en el mismo teclado. | v1 |
| RF-02 | Un jugador puede poner una papa bomba en su casilla; explota en cruz a los 2,5 s. | v1 |
| RF-03 | La explosión rompe cajas, destruye poderes sueltos y hace explotar otras papas (reacción en cadena). | v1 |
| RF-04 | Un jugador puede tirar una papa 3 casillas hacia donde mira, o recoger y tirar una que esté en su casilla. | v1 |
| RF-05 | Cada jugador tiene un cañón con 3 balas que se recargan una cada 6 s. Una bala deja frito al rival. | v1 |
| RF-06 | Las cajas pueden esconder poderes: más alcance, más papas o más velocidad. | v1 |
| RF-07 | A los 90 s empieza la muerte súbita: la cancha se cierra desde los bordes y las balas son ilimitadas. | v1 |
| RF-08 | Un jugador alcanzado por el fuego, una bala o un muro que se cierra pierde la ronda. | v1 |
| RF-09 | Gana la partida el primero en ganar 3 rondas. | v1 |
| RF-10 | El buzzer, el LED y el botón del GrovePi+ reaccionan a los eventos del juego. | v1 |
| RF-11 | Un jugador puede jugar contra la CPU. | v2 |
| RF-12 | Hay un menú principal con: 2 jugadores, 1 jugador vs CPU, cómo jugar y salir. | v2 |
| RF-13 | El juego se puede pausar y, desde la pausa, volver al menú. | v2 |
| RF-14 | Cada ronda empieza con una cuenta regresiva. | v2 |
| RF-15 | Hay tres canchas distintas que rotan por ronda. | v2 |
| RF-16 | El juego emite efectos de sonido por el parlante. | v2 |
| RF-17 | Se puede alternar entre ventana y pantalla completa. | v2 |
| RF-18 | Cada cancha tiene su propio ambiente visual (colores, muros y objetos que se rompen). | v3 |
| RF-19 | La cafetería tiene mesas en vez de cajas y personajes no jugables sirviendo comida. | v3 |

## Requisitos no funcionales

| ID | Requisito | Cómo se cumple |
|---|---|---|
| RNF-01 | **Plataforma:** debe correr en una Raspberry Pi 3. | Python + pygame, 660×628 a 30 cuadros por segundo. |
| RNF-02 | **Rendimiento:** no debe trabarse en la Pi. | Capa fija para el escenario, textos en memoria, sombras sin transparencia y tope de partículas. |
| RNF-03 | **Tolerancia a hardware ausente:** debe funcionar sin GrovePi+ y sin parlante. | Ambos son opcionales; si fallan, el juego avisa por consola y sigue. |
| RNF-04 | **Portabilidad:** debe poder copiarse fácil a la Pi. | Un solo archivo, sin imágenes ni audios. |
| RNF-05 | **Identidad visual:** paleta roja y blanca y personajes encapuchados. | Personajes, barra superior y menús en rojo y blanco. |
| RNF-06 | **Justicia:** ninguno de los dos jugadores debe salir con ventaja. | Canchas, cajas y poderes simétricos; la muerte súbita cierra casillas de a pares espejo. |
| RNF-07 | **Usabilidad:** se debe poder aprender a jugar sin leer el código. | Pantalla de cómo jugar y controles visibles en el menú. |
| RNF-08 | **Mantenibilidad:** debe ser fácil de ajustar. | Constantes al inicio del archivo; canchas en `LAYOUTS` y ambientes en `THEMES`. |
| RNF-09 | **Compatibilidad:** debe servir con pygame 1.9 y 2. | No usa funciones exclusivas de pygame 2. |

El estado de verificación de cada uno está en [PRUEBAS.md](PRUEBAS.md).
