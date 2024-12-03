const puppeteer = require('puppeteer');
const { Kafka, logLevel, Partitioners } = require('kafkajs');

const kafka = new Kafka({
  clientId: 'waze-scraper',
  brokers: ['localhost:9092'],
  logLevel: logLevel.WARN
});
const producer = kafka.producer({
  createPartitioner: Partitioners.LegacyPartitioner
});

(async () => {
  try {
    await producer.connect();

    const browser = await puppeteer.launch({
      headless: true, // Cambiar a true para evitar problemas gráficos
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    

    const locations = [
      { name: 'Santiago, Chile', url: 'https://www.waze.com/en/live-map/directions?latlng=-33.43785195054054%2C-70.6203317642212' },
      { name: 'Tokio, Japón', url: 'https://www.waze.com/en/live-map/directions?latlng=35.676755415954865%2C139.76290047168735' },
      { name: 'Buenos Aires, Argentina', url: 'https://www.waze.com/en/live-map/directions?latlng=-34.621474985215016%2C-58.38730216026307' },
      { name: 'Brasilia, Brasil', url: 'https://www.waze.com/en/live-map/directions?latlng=-15.80602514998607%2C-47.8964638710022' },
      { name: 'Washington, D.C., Estados Unidos', url: 'https://www.waze.com/en/live-map/directions?latlng=38.88490315007399%2C-77.01117753982545' },
      { name: 'Guadalajara, México', url: 'https://www.waze.com/en/live-map/directions?latlng=20.643477185724606%2C-103.37957739830017' }
    ];

    for (const location of locations) {
      console.log(`Accediendo a ${location.name}`);
      const page = await browser.newPage();
      await page.goto(location.url, { waitUntil: 'networkidle2' });

      try {
        await page.waitForSelector('button.waze-tour-tooltip__acknowledge', { timeout: 5000 });
        await page.click('button.waze-tour-tooltip__acknowledge');
        console.log("Botón 'Entendido' encontrado y clickeado.");
      } catch (error) {
        console.log("Botón 'Entendido' no encontrado o ya fue clickeado.");
      }

      await new Promise(resolve => setTimeout(resolve, 5000));

      const zoomOutButton = await page.$('a.leaflet-control-zoom-out');
      if (zoomOutButton) {
        for (let i = 0; i < 3; i++) {
          await zoomOutButton.click();
          await new Promise(resolve => setTimeout(resolve, 500));
        }
        console.log(`Zoom ajustado para ${location.name}.`);
      } else {
        console.log("Botón de 'Alejar' no encontrado.");
      }

      const onResponse = async (response) => {
        const url = response.url();
        if (url.includes('alerts')) {
          try {
            const data = await response.json();
            if (data.alerts) {
              const startTime = Date.now(); // Inicio de medición de latencia
              for (const alert of data.alerts) {
                const enrichedAlert = {
                  ...alert,
                  generated_at: new Date().toISOString(), // Timestamp del envío
                };

                await producer.send({
                  topic: 'waze-alerts',
                  messages: [{ value: JSON.stringify(enrichedAlert) }]
                });
                const endTime = Date.now(); // Fin de medición de latencia
                const latency = endTime - startTime;
                console.log(`Enviado a Kafka desde ${location.name}: ${alert.type} en ${alert.city}. Latencia: ${latency} ms`);
              }
            }
          } catch (error) {
            console.error('Error procesando la respuesta:', error);
          }
        }
      };

      page.on('response', onResponse);

      await new Promise(resolve => setTimeout(resolve, 10000));
      page.off('response', onResponse); 
      await page.close(); 
    }

    await producer.disconnect();
    await browser.close();
  } catch (error) {
    console.error('Error en el proceso de scraping:', error);
  }
})();
