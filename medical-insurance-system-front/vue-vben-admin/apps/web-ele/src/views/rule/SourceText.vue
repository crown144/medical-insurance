<script lang="ts" setup>
// Source documents are untrusted data, including previously stored records.
// Render markup as text so scripts, handlers and links cannot become active DOM.
defineProps<{ content: string }>();
</script>

<template>
  <pre class="source-text">{{ content }}</pre>
</template>

<style scoped>
.source-text {
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
