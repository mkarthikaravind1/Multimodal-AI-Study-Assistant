import api from "./axios";

// Original uploaded files are fetched with the auth header and turned into
// object URLs (a plain <a href> / <video src> can't send the JWT).
// Cached per material so re-opening a citation doesn't re-download it.
const cache = new Map(); // material_id -> Promise<objectUrl>

export function getMaterialFileUrl(materialId) {
  if (!cache.has(materialId)) {
    const promise = api
      .get(`/upload/materials/${materialId}/file`, { responseType: "blob" })
      .then((res) => URL.createObjectURL(res.data))
      .catch((err) => {
        cache.delete(materialId); // allow a retry
        throw err;
      });
    cache.set(materialId, promise);
  }
  return cache.get(materialId);
}
