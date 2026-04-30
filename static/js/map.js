// static/js/map.js

document.addEventListener('DOMContentLoaded', function () {

  const mapDiv = document.getElementById('donor-map');
  if (!mapDiv) return;

  // Init map — center on Visakhapatnam area
  const map = L.map('donor-map', { zoomControl: true })
               .setView([17.6868, 83.2185], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 18
  }).addTo(map);

  // Custom red drop icon
  const redIcon = L.divIcon({
    className: '',
    html: `<div style="width:22px;height:30px;">
             <svg viewBox="0 0 24 32" xmlns="http://www.w3.org/2000/svg">
               <path d="M12 0 C12 0 2 10 2 18 A10 10 0 0 0 22 18 C22 10 12 0 12 0Z"
                     fill="#C0392B" stroke="#922b21" stroke-width="1"/>
               <circle cx="12" cy="18" r="4" fill="white" opacity="0.7"/>
             </svg>
           </div>`,
    iconSize:   [22, 30],
    iconAnchor: [11, 30],
    popupAnchor:[0, -30]
  });

  // Blue hospital icon
  const blueIcon = L.divIcon({
    className: '',
    html: `<div style="width:26px;height:34px;">
             <svg viewBox="0 0 24 32" xmlns="http://www.w3.org/2000/svg">
               <path d="M12 0 C12 0 2 10 2 18 A10 10 0 0 0 22 18 C22 10 12 0 12 0Z"
                     fill="#2980b9" stroke="#1a5276" stroke-width="1"/>
               <text x="12" y="21" text-anchor="middle"
                     font-size="10" fill="white" font-weight="bold">H</text>
             </svg>
           </div>`,
    iconSize:   [26, 34],
    iconAnchor: [13, 34]
  });

  // Marker cluster group
  const clusterGroup = L.markerClusterGroup({
    iconCreateFunction: function(cluster) {
      return L.divIcon({
        html: `<div style="background:#C0392B;color:#fff;border-radius:50%;
                           width:36px;height:36px;display:flex;
                           align-items:center;justify-content:center;
                           font-weight:700;font-size:13px;
                           border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);">
                 ${cluster.getChildCount()}
               </div>`,
        iconSize: [36, 36]
      });
    }
  });

  let radiusCircle = null;
  let hospitalPin  = null;

  // Load donors from API (placeholder for actual API endpoint if exists)
  function loadDonors(filterGroup = null) {
    // This function can be expanded to fetch real donor data
    // For now, it might be triggered by seeker dashboard or directory page
  }

  // Draw 10km circle around hospital/request
  function drawRadiusCircle(lat, lng) {
    if (radiusCircle) map.removeLayer(radiusCircle);
    if (hospitalPin)  map.removeLayer(hospitalPin);

    radiusCircle = L.circle([lat, lng], {
      radius      : 10000,
      color       : '#C0392B',
      fillColor   : '#C0392B',
      fillOpacity : 0.05,
      weight      : 2,
      dashArray   : '6,4'
    }).addTo(map);

    hospitalPin = L.marker([lat, lng], { icon: blueIcon })
      .bindPopup('<b>Request Location</b><br>10km search radius')
      .addTo(map);

    map.setView([lat, lng], 13);
  }

  // Auto-locate user
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      // map.setView([pos.coords.latitude, pos.coords.longitude], 11);
    });
  }

  window.drawRadiusCircle = drawRadiusCircle;

  // If page has request context
  if (mapDiv.dataset.lat && mapDiv.dataset.lng) {
    drawRadiusCircle(
      parseFloat(mapDiv.dataset.lat),
      parseFloat(mapDiv.dataset.lng)
    );
  }
});
