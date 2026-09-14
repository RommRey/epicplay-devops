<template>
  <v-app theme="dark">
    <v-app-bar flat border>
      <v-app-bar-title class="font-weight-bold">
        📷 EpicPlay — Pipeline de Procesamiento Deportivo
      </v-app-bar-title>
      <v-spacer></v-spacer>
      <v-chip color="success" size="small" variant="flat">Entorno Local Activo</v-chip>
    </v-app-bar>

    <v-main class="bg-grey-darken-4">
      <v-container fluid class="pa-6">
        
        <!-- DASHBOARD DE MÉTRICAS (FASE 2.1) -->
        <v-row class="mb-4">
          <v-col cols="12" sm="3">
            <v-card variant="outlined" class="pa-4 border-grey">
              <div class="text-caption text-grey">Total Fotografías</div>
              <div class="text-h4 font-weight-bold primary--text">{{ metricas.total_fotos || 0 }}</div>
            </v-card>
          </v-col>
          <v-col cols="12" sm="3">
            <v-card variant="outlined" class="pa-4 border-success">
              <div class="text-caption text-grey">Procesadas (4:5 sRGB)</div>
              <div class="text-h4 font-weight-bold text-success">{{ metricas.procesadas || 0 }}</div>
            </v-card>
          </v-col>
          <v-col cols="12" sm="3">
            <v-card variant="outlined" class="pa-4 border-error">
              <div class="text-caption text-grey">Descartadas (Blur)</div>
              <div class="text-h4 font-weight-bold text-error">{{ metricas.descartadas || 0 }}</div>
            </v-card>
          </v-col>
          <v-col cols="12" sm="3">
            <v-card variant="outlined" class="pa-4 border-info">
              <div class="text-caption text-grey">Tiempo Promedio</div>
              <div class="text-h4 font-weight-bold text-info">
                {{ Math.round(metricas.tiempo_promedio_ms || 0) }} ms
              </div>
            </v-card>
          </v-col>
        </v-row>

        <!-- SUBIDA MASIVA -->
        <v-card class="mb-6 pa-4" variant="outlined">
          <v-card-title class="text-h6">Subida Masiva de Fotografías Deportivas</v-card-title>
          <v-card-subtitle>Envía las fotos del partido al pipeline (Filtro Blur + YOLOv8 + Recorte Nativo + Color GIMP).</v-card-subtitle>
          <v-card-text>
            <v-file-input
              v-model="archivos"
              label="Seleccionar fotografías (JPG/PNG)"
              multiple
              accept="image/*"
              prepend-icon="mdi-camera"
              variant="outlined"
            ></v-file-input>
            <v-btn
              color="primary"
              :loading="cargando"
              :disabled="!archivos || archivos.length === 0"
              @click="procesarImagenes"
            >
              🚀 Procesar Fotografías
            </v-btn>
          </v-card-text>
        </v-card>

        <!-- HISTORIAL Y CONSULTAS SQL -->
        <v-card variant="outlined">
          <v-card-title class="d-flex align-center py-3">
            <span>Historial de Procesamiento (PostgreSQL)</span>
            <v-spacer></v-spacer>
            
            <!-- FILTROS SQL -->
            <v-btn-toggle v-model="filtroEstado" mandatory size="small" variant="outlined" @update:model-value="cargarDatos">
              <v-btn value="">Todas</v-btn>
              <v-btn value="procesada" color="success">Procesadas</v-btn>
              <v-btn value="descartada" color="error">Descartadas</v-btn>
            </v-btn-toggle>
          </v-card-title>

          <v-divider></v-divider>

          <v-data-table
            :headers="headers"
            :items="fotografias"
            :loading="cargandoTabla"
            no-data-text="No hay fotografías procesadas aún."
            class="bg-transparent"
          >
            <template v-slot:item.es_nitida="{ item }">
              <v-chip :color="item.es_nitida ? 'success' : 'error'" size="small">
                {{ item.es_nitida ? 'NÍTIDA' : 'BORROSA' }}
              </v-chip>
            </template>

            <template v-slot:item.estado="{ item }">
              <v-chip :color="item.estado === 'procesada' ? 'success' : 'error'" variant="outlined" size="small">
                {{ item.estado }}
              </v-chip>
            </template>

            <template v-slot:item.tiempo_ejecucion_ms="{ item }">
              {{ item.tiempo_ejecucion_ms }} ms
            </template>
          </v-data-table>
        </v-card>

      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API_URL = 'http://localhost:8000/api'

const archivos = ref([])
const cargando = ref(false)
const cargandoTabla = ref(false)
const filtroEstado = ref('')
const fotografias = ref([])
const metricas = ref({})

const headers = [
  { title: 'ID', key: 'id' },
  { title: 'Archivo', key: 'nombre_archivo' },
  { title: 'Estado Nitidez', key: 'es_nitida' },
  { title: 'Varianza Laplaciana', key: 'varianza_laplaciana' },
  { title: 'Estado Pipeline', key: 'estado' },
  { title: 'Tiempo Exec.', key: 'tiempo_ejecucion_ms' }
]

const cargarMetricas = async () => {
  try {
    const response = await fetch(`${API_URL}/metricas`)
    if (response.ok) {
      metricas.value = await response.json()
    }
  } catch (e) {
    console.error("Error al cargar métricas:", e)
  }
}

const cargarDatos = async () => {
  cargandoTabla.value = true
  try {
    const url = filtroEstado.value 
      ? `${API_URL}/fotografias?estado=${filtroEstado.value}` 
      : `${API_URL}/fotografias`
    const response = await fetch(url)
    if (response.ok) {
      fotografias.value = await response.json()
    }
  } catch (e) {
    console.error("Error al cargar historial:", e)
  } finally {
    cargandoTabla.value = false
  }
}

const procesarImagenes = async () => {
  if (!archivos.value || archivos.value.length === 0) return
  cargando.value = true

  for (const file of archivos.value) {
    const formData = new FormData()
    formData.append('file', file)

    try {
      await fetch(`${API_URL}/procesar-foto`, {
        method: 'POST',
        body: formData
      })
    } catch (e) {
      console.error("Error al procesar:", e)
    }
  }

  archivos.value = []
  cargando.value = false
  await cargarDatos()
  await cargarMetricas()
}

onMounted(() => {
  cargarDatos()
  cargarMetricas()
})
</script>