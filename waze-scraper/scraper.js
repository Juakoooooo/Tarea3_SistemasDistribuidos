const puppeteer = require('puppeteer');
const { Kafka, logLevel, Partitioners } = require('kafkajs');

// Configuración de Kafka
const kafka = new Kafka({
  clientId: 'waze-scraper',
  brokers: ['localhost:9092'],
  logLevel: logLevel.WARN
});
const producer = kafka.producer({
    createPartitioner: Partitioners.LegacyPartitioner // Agrega esta opción
  });
(async () => {
  try {
    // Conectar el productor de Kafka
    await producer.connect();

    // Configurar Puppeteer y abrir navegador
    const browser = await puppeteer.launch({
      headless: false,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    // Navegar a la página de Waze y esperar a que cargue
    await page.goto('https://www.waze.com/livemap', { waitUntil: 'networkidle2' });
    
    // Pausa de 5 segundos usando setTimeout
    await new Promise(resolve => setTimeout(resolve, 5000));

    // Función para simular movimientos en el mapa
    async function moveMap() {
      // Coordenadas de ejemplo para moverse a diferentes ubicaciones
      const locations = [
        { xOffset: 100, yOffset: 100 },  // Mover a la derecha y abajo
        { xOffset: -100, yOffset: -100 }, // Mover a la izquierda y arriba
        { xOffset: 200, yOffset: 0 },    // Mover a la derecha
        { xOffset: -200, yOffset: 0 }    // Mover a la izquierda
      ];

      for (const { xOffset, yOffset } of locations) {
        // Simular arrastre del mapa
        await page.mouse.move(300, 300);
        await page.mouse.down();
        await page.mouse.move(300 + xOffset, 300 + yOffset, { steps: 10 });
        await page.mouse.up();

        console.log(`Movido el mapa con desplazamiento x: ${xOffset}, y: ${yOffset}`);

        // Pausa de 10 segundos en cada movimiento usando setTimeout
        await new Promise(resolve => setTimeout(resolve, 10000));
      }
    }

    // Función para escuchar respuestas de red y enviar alertas a Kafka
    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('alerts')) {
        try {
          const data = await response.json();
          if (data.alerts) {
            for (const alert of data.alerts) {
              await producer.send({
                topic: 'waze-alerts',
                messages: [{ value: JSON.stringify(alert) }]
              });
              console.log(`Enviado a Kafka: ${alert.type} en ${alert.city}`);
            }
          }
        } catch (error) {
          console.error('Error procesando la respuesta:', error);
        }
      }
    });

    // Ejecutar la función de movimientos en el mapa
    await moveMap();

    // Espera de 10 segundos adicionales para capturar alertas después de moverse
    await new Promise(resolve => setTimeout(resolve, 10000));

    // Cerrar productor de Kafka y navegador
    await producer.disconnect();
    await browser.close();
  } catch (error) {
    console.error('Error en el proceso de scraping:', error);
  }
})();
