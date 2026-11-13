# Pruebas

## Cómo se probó

Las versiones 2 y 3 se probaron con **simulación automática sin pantalla**: el juego se ejecuta con los controladores de video y audio falsos de SDL (`SDL_VIDEODRIVER=dummy`), avanzando la lógica miles de cuadros con dos CPU jugando entre sí. Así se recorren muchas más situaciones de las que alcanza a jugar una persona, y cualquier error de ejecución detiene la prueba.

**Entorno:** PC con Windows 11, Python 3.14 y pygame-ce 2.5.

## Resultados

| Prueba | Qué verifica | Resultado |
|---|---|---|
| Más de 100 rondas de CPU contra CPU (60 000 cuadros por tanda) | Que la lógica no falle: explosiones, cadenas, tiros, balas, poderes, muerte súbita | Sin errores |
| Partida completa contra la CPU | Que se pase por todos los estados: menú, cómo jugar, cuenta regresiva, ronda, fin de ronda, campeón, pausa y vuelta al menú | Correcto |
| Equilibrio entre los dos lados (76 rondas) | Que la cancha no favorezca a ninguno | ROJO 25, BLANCO 27, empates 24 |
| Duración de las rondas (76 rondas) | Que las rondas no sean eternas ni instantáneas | Mediana de 59 s; 22 llegaron a muerte súbita |
| Arranque real con ventana y audio | Que `main()` abra, juegue y cierre limpio | Correcto |
| Las tres canchas por separado (v3) | Que cada ambiente se dibuje bien y sin errores | Correcto, revisado en capturas |
| Tiempo por cuadro en cada cancha (v3) | Que los ambientes nuevos no vuelvan lento el juego | Menos de 1 ms de dibujo por cuadro en el PC, igual en las tres |
| Reconstrucción de la v2 | Que el archivo `versiones/v2_papas_bomba.py` sea jugable | Pasa la misma simulación completa |

## Qué falta por probar

Estas pruebas necesitan el hardware real y no se han hecho:

| Pendiente | Por qué importa |
|---|---|
| Correr el juego en la Raspberry Pi 3 | El rendimiento se midió en un PC, que es mucho más rápido |
| GrovePi+: buzzer, LED y botón | El código es el mismo de la v1, pero no se ha comprobado con la tarjeta en las versiones 2 y 3 |
| Sonido por el parlante de la Pi | Depende de la salida de audio configurada |
| Pantalla completa (`-f` y F11) | Se comporta distinto según la versión de pygame |
| Dos personas en el mismo teclado | Algunos teclados no registran más de 3 o 4 teclas a la vez |
| pygame 1.9 | El código evita lo exclusivo de pygame 2, pero no se ha corrido en esa versión |

## Limitaciones conocidas

- **Muchos empates entre CPUs:** cerca de 3 de cada 10 rondas de CPU contra CPU terminan con los dos fritos, casi siempre en la muerte súbita.
- **La CPU no esquiva las balas:** solo huye del fuego y de los muros que se cierran.
- **Una sola dificultad** de CPU.
- **Sin mandos:** solo teclado y el botón Grove.
