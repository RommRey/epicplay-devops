<template>
  <v-app theme="dark">
    <!-- Encabezado con Logo Oficial de EpicPlay importado desde src/assets -->
    <v-app-bar flat border color="#121212">
      <div class="d-flex align-center ml-4">
        <v-avatar size="42" class="mr-3">
          <v-img :src="logoEpicPlay" alt="EpicPlay Logo"></v-img>
        </v-avatar>
        <span class="font-weight-bold text-h5 text-white">EpicPlay Engine</span>
      </div>
    </v-app-bar>

    <v-main class="bg-grey-darken-4 pa-6">
      <v-container max-width="1200">
        
        <!-- Panel 1: Selección de Formatos -->
        <v-card class="pa-4 mb-6" elevation="3" rounded="lg">
          <v-card-title class="text-h6 font-weight-bold d-flex align-center">
            <v-icon icon="mdi-crop" class="mr-2" color="primary"></v-icon>
            Formatos de Salida
          </v-card-title>
          <v-card-text>
            <v-row dense>
              <v-col cols="12" sm="4">
                <v-checkbox
                  v-model="formatosSeleccionados"
                  label="Instagram (4:5 / 1080x1350)"
                  value="instagram"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
              <v-col cols="12" sm="4">
                <v-checkbox
                  v-model="formatosSeleccionados"
                  label="Galería Web (Protegida)"
                  value="galeria_web"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
              <v-col cols="12" sm="4">
                <v-checkbox
                  v-model="formatosSeleccionados"
                  label="Impresión 4x6 (2:3)"
                  value="impresion"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
              <v-col cols="12" sm="4">
                <v-checkbox
                  v-model="formatosSeleccionados"
                  label="Credencial / Sticker"
                  value="credencial"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
              <v-col cols="12" sm="4">
                <v-checkbox
                  v-model="formatosSeleccionados"
                  label="iPad / Tablet (3:4)"
                  value="ipad"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Panel 2: Zona Drag & Drop / Explorador de Archivos -->
        <v-card class="pa-4 mb-6" elevation="3" rounded="lg">
          <v-card-title class="text-h6 font-weight-bold d-flex align-center">
            <v-icon icon="mdi-cloud-upload" class="mr-2" color="primary"></v-icon>
            Cargar Fotografías
          </v-card-title>
          <v-card-text>
            <!-- Dropzone para arrastrar o hacer clic -->
            <div
              class="dropzone pa-8 text-center rounded-lg border-dashed"
              :class="{ 'dropzone-active': isDragging }"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="handleDrop"
              @click="triggerFileSelect"
            >
              <input
                ref="fileInput"
                type="file"
                multiple
                accept="image/*,.cr3,.cr2,.nef,.arw,.dng,.heic"
                class="d-none"
                @change="handleFileSelect"
              />
              <v-icon icon="mdi-cloud-upload-outline" size="56" color="primary" class="mb-2"></v-icon>
              <div class="text-h6 font-weight-medium">
                Arrastra las fotografías aquí o haz clic para seleccionar
              </div>
              <div class="text-caption text-grey-lighten-1 mt-1">
                Admite JPG, PNG, CR3, RAW y HEIC (puedes seleccionar varios archivos a la vez)
              </div>
            </div>

            <!-- Lista de Archivos Seleccionados -->
            <div v-if="archivosSeleccionados.length > 0" class="mt-4">
              <div class="text-subtitle-2 font-weight-bold mb-2">
                Archivos listos para procesar ({{ archivosSeleccionados.length }}):
              </div>
              <v-chip-group column>
                <v-chip
                  v-for="(file, index) in archivosSeleccionados"
                  :key="index"
                  closable
                  color="primary"
                  variant="outlined"
                  @click:close="removerArchivo(index)"
                >
                  {{ file.name }}
                </v-chip>
              </v-chip-group>

              <v-btn
                color="primary"
                size="large"
                block
                class="mt-4"
                :loading="procesando"
                :disabled="formatosSeleccionados.length === 0"
                @click="procesarFotografias"
              >
                <v-icon icon="mdi-play" class="mr-2"></v-icon>
                Iniciar Pipeline
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <!-- Panel 3: Historial en Base de Datos -->
        <v-card elevation="3" rounded="lg">
          <v-card-title class="d-flex justify-space-between align-center pa-4">
            <div class="d-flex align-center text-h6 font-weight-bold">
              <v-icon icon="mdi-history" class="mr-2" color="primary"></v-icon>
              Historial de Procesamiento
            </div>
            <v-btn
              color="error"
              variant="text"
              prepend-icon="mdi-delete-sweep"
              :disabled="historial.length === 0"
              @click="limpiarHistorial"
            >
              Limpiar Todo
            </v-btn>
          </v-card-title>

          <v-divider></v-divider>

          <v-table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Archivo</th>
                <th>Estado</th>
                <th>Varianza</th>
                <th>Tiempo</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="historial.length === 0">
                <td colspan="6" class="text-center text-grey py-4">
                  No hay fotografías registradas en el historial.
                </td>
              </tr>
              <tr v-for="item in historial" :key="item.id">
                <td>#{{ item.id }}</td>
                <td class="font-weight-medium">{{ item.nombre_archivo }}</td>
                <td>
                  <v-chip
                    :color="item.estado === 'procesada' ? 'success' : 'error'"
                    size="small"
                    label
                  >
                    {{ item.estado }}
                  </v-chip>
                </td>
                <td>{{ item.varianza_laplaciana }}</td>
                <td>{{ item.tiempo_ms }} ms</td>
                <td>
                  <v-btn
                    icon="mdi-delete"
                    size="small"
                    color="error"
                    variant="text"
                    @click="eliminarFoto(item.id)"
                  ></v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>

      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// Importar el logo
import logoEpicPlay from './assets/EP_Logo_circle_HD .png'

// Variables Reactivas
const fileInput = ref(null)
const isDragging = ref(false)
const archivosSeleccionados = ref([]) // Aquí guardaremos los RAWs/JPGs
const formatosSeleccionados = ref(['instagram', 'galeria_web', 'impresion', 'credencial', 'ipad'])
const procesando = ref(false)
const historial = ref([]) 

const API_BASE = 'http://localhost:8000/api'

// --- EVENTOS DEL DRAG & DROP Y SELECCIÓN DE ARCHIVOS ---

// 1. Abre el explorador de Windows al hacer clic en el recuadro
const triggerFileSelect = () => {
  if (fileInput.value) {
    fileInput.value.click()
  }
}

// 2. Captura los archivos cuando los seleccionas en el explorador
const handleFileSelect = (event) => {
  const target = event.target
  if (target.files && target.files.length > 0) {
    // Agrega los nuevos archivos a la lista (respeta si ya había otros cargados)
    const nuevosArchivos = Array.from(target.files)
    archivosSeleccionados.value = [...archivosSeleccionados.value, ...nuevosArchivos]
    // Limpiar el input para permitir seleccionar el mismo archivo si se elimina
    target.value = ''
  }
}

// 3. Captura los archivos si los arrastras desde una carpeta y los sueltas
const handleDrop = (event) => {
  isDragging.value = false
  if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
    const nuevosArchivos = Array.from(event.dataTransfer.files)
    archivosSeleccionados.value = [...archivosSeleccionados.value, ...nuevosArchivos]
  }
}

// 4. Quitar un archivo de la lista antes de procesar
const removerArchivo = (index) => {
  archivosSeleccionados.value.splice(index, 1)
}

// 5. Limpiar historial visual
const limpiarHistorial = () => {
  if (historial.value) {
    historial.value = []
  }
}


// --- CONEXIÓN CON EL BACKEND (FASTAPI / POSTGRESQL) ---

const cargarHistorial = async () => {
  try {
    const res = await fetch(`${API_BASE}/fotografias`)
    if (res.ok) {
      const datos = await res.json()
      historial.value = datos 
    } else {
      console.error("Error al obtener datos de la API:", res.statusText)
    }
  } catch (err) {
    console.error("Error de red al conectar con el backend:", err)
  }
}

const procesarFotografias = async () => {
  if (archivosSeleccionados.value.length === 0) return
  procesando.value = true

  try {
    const formData = new FormData()
    archivosSeleccionados.value.forEach(file => {
      formData.append('files', file)
    })
    formData.append('formatos', formatosSeleccionados.value.join(','))

    const res = await fetch(`${API_BASE}/procesar-foto`, {
      method: 'POST',
      body: formData
    })

    if (res.ok) {
      archivosSeleccionados.value = [] // Limpia la lista al terminar
      await cargarHistorial()          // Refresca la tabla
    } else {
      const errData = await res.json()
      alert(`Error: ${errData.detail || 'No se pudo procesar'}`)
    }
  } catch (err) {
    alert('Ocurrió un fallo al comunicarse con la API')
  } finally {
    procesando.value = false
  }
}

const eliminarFoto = async (id) => {
  try {
    const res = await fetch(`${API_BASE}/fotografias/${id}`, { method: 'DELETE' })
    if (res.ok) {
      await cargarHistorial()
    }
  } catch (err) {
    console.error('Error al eliminar:', err)
  }
}

// Ejecutar al cargar la página
onMounted(() => {
  cargarHistorial()
})
</script>

<style scoped>
.dropzone {
  border: 2px dashed #424242;
  background-color: #1e1e1e;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}
.dropzone:hover {
  border-color: #2196f3;
  background-color: #262626;
}
.dropzone-active {
  border-color: #4caf50;
  background-color: #1b3821;
}
</style>