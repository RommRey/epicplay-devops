<template>
  <v-app>
    <!-- Barra Superior -->
    <v-app-bar color="indigo-darken-4" elevation="2">
      <v-app-bar-title class="font-weight-bold">
        📸 EpicPlay — Pipeline de Procesamiento
      </v-app-bar-title>
      <v-chip color="success" size="small" class="mr-4">Entorno Local Activo</v-chip>
    </v-app-bar>

    <v-main class="bg-grey-lighten-4">
      <v-container class="py-8">
        
        <!-- Panel de Carga de Archivos -->
        <v-card elevation="2" class="pa-6 mb-6 rounded-lg">
          <v-card-title class="text-h6 font-weight-bold">
            Subida Masiva de Fotografías Deportivas
          </v-card-title>
          <v-card-subtitle class="mb-4">
            Envía las fotos del partido al pipeline (Filtro Blur + YOLOv8n + Recorte + Resize).
          </v-card-subtitle>

          <v-file-input
            v-model="archivosSeleccionados"
            label="Seleccionar fotografías (JPG/PNG)"
            accept="image/*"
            multiple
            prepend-icon="mdi-camera"
            variant="outlined"
            show-size
            chips
            :disabled="procesando"
          ></v-file-input>

          <div class="d-flex justify-end mt-2">
            <v-btn
              color="primary"
              size="large"
              prepend-icon="mdi-cog-play"
              :loading="procesando"
              :disabled="!archivosSeleccionados.length"
              @click="procesarLote"
            >
              Procesar Fotografías
            </v-btn>
          </div>
        </v-card>

        <!-- Tabla de Historial en PostgreSQL -->
        <v-card elevation="2" class="pa-6 rounded-lg">
          <v-card-title class="text-h6 font-weight-bold mb-4">
            Historial de Procesamiento (PostgreSQL)
          </v-card-title>

          <v-data-table
            :headers="headers"
            :items="historial"
            no-data-text="No hay fotografías procesadas aún."
            class="elevation-0"
          >
            <template v-slot:item.es_nitida="{ item }">
              <v-chip
                :color="item.es_nitida ? 'success' : 'error'"
                size="small"
                class="font-weight-bold"
              >
                {{ item.es_nitida ? 'NÍTIDA' : 'BORROSA' }}
              </v-chip>
            </template>

            <template v-slot:item.varianza="{ item }">
              <code>{{ item.varianza }}</code>
            </template>

            <template v-slot:item.tiempo_ms="{ item }">
              <span>{{ item.tiempo_ms }} ms</span>
            </template>
          </v-data-table>
        </v-card>

      </v-container>
    </v-main>
  </v-app>
</template>

<script>
export default {
  data() {
    return {
      archivosSeleccionados: [],
      procesando: false,
      historial: [],
      headers: [
        { title: 'ID', key: 'id' },
        { title: 'Archivo', key: 'nombre' },
        { title: 'Estado Nitidez', key: 'es_nitida' },
        { title: 'Varianza Laplaciana', key: 'varianza' },
        { title: 'Estado Pipeline', key: 'estado' },
        { title: 'Tiempo Exec.', key: 'tiempo_ms' }
      ]
    }
  },
  mounted() {
    this.cargarHistorial();
  },
  methods: {
    async cargarHistorial() {
      try {
        const res = await fetch('http://localhost:8000/api/fotografias');
        if (res.ok) {
          this.historial = await res.json();
        }
      } catch (err) {
        console.error('Error al conectar con la API:', err);
      }
    },
    async procesarLote() {
      if (!this.archivosSeleccionados.length) return;
      
      this.procesando = true;

      for (const archivo of this.archivosSeleccionados) {
        const formData = new FormData();
        formData.append('file', archivo);

        try {
          await fetch('http://localhost:8000/api/procesar-foto', {
            method: 'POST',
            body: formData
          });
        } catch (err) {
          console.error(`Error procesando ${archivo.name}:`, err);
        }
      }

      this.archivosSeleccionados = [];
      this.procesando = false;
      await this.cargarHistorial();
    }
  }
}
</script>