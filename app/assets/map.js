// Funções usadas pelas camadas GeoJSON do dash-leaflet (referenciadas por nome no Python).
(function () {
  let palette = null;

  function colors() {
    if (!palette) {
      const css = getComputedStyle(document.documentElement);
      const read = (name) => css.getPropertyValue(name).trim();
      palette = {
        accepted: read("--courier-accepted"),
        rejected: read("--courier-rejected"),
        other: read("--courier-other"),
      };
    }
    return palette;
  }

  window.courierMap = Object.assign({}, window.courierMap, {
    fleetPoint: function (feature, latlng) {
      return L.circleMarker(latlng, {
        pane: "fleet",
        radius: 3,
        stroke: false,
        fillColor: colors().other,
        fillOpacity: 0.6,
        interactive: false,
      });
    },
    candidatePoint: function (feature, latlng) {
      const p = feature.properties;
      if (p.accepted && p.dense) {
        return L.circleMarker(latlng, {
          pane: "candidates",
          radius: 4,
          stroke: false,
          fillColor: colors().accepted,
          fillOpacity: 0.9,
        }).bindTooltip(p.tip, { direction: "top", offset: [0, -4] });
      }
      const marker = p.accepted
        ? L.circleMarker(latlng, {
            pane: "candidates",
            radius: 7,
            color: "#ffffff",
            weight: 2,
            fillColor: colors().accepted,
            fillOpacity: 1,
          })
        : L.circleMarker(latlng, {
            pane: "candidates",
            radius: 5,
            stroke: false,
            fillColor: colors().rejected,
            fillOpacity: 0.85,
          });
      return marker.bindTooltip(p.tip, { direction: "top", offset: [0, -6] });
    },
  });
})();
