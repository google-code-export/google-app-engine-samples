var console = console || {};
console.log = console.log || function(data) { }

var geoserver = {};

geoserver.adminPanel = function(id) {
  this.map_ = null;
  this.dom_ = {
    wrapper_div: document.getElementById(id),
    sidebar_divs: []
  }
  this.selected_geometry_ = null;
  this.geometries_ = [];
  this.mode_ = 'view';
  this.createMap_();
};

geoserver.adminPanel.prototype.createMap_ = function() {
  var me = this;
  var table = document.createElement('table');
  table.style.width = '100%';
  var tr = document.createElement('tr');
  var map_td = document.createElement('td');
  map_td.width = '70%';
  var map_div = document.createElement('div');
  map_div.style.height = '700px';
  map_div.style.border = '1px solid grey';
  map_td.appendChild(map_div);
  var sidebar_td = document.createElement('td');
  sidebar_td.width = '29%';
  var sidebar_div = document.createElement('div');
  sidebar_div.style.height = '700px';
  sidebar_div.style.overflow = 'auto';
  sidebar_div.style.border = '1px solid grey';
  sidebar_td.appendChild(sidebar_div);
  tr.appendChild(map_td);
  tr.appendChild(sidebar_td);
  table.appendChild(tr);
  this.dom_.wrapper_div.appendChild(table);
  this.dom_.sidebar_div = sidebar_div;
 
  this.map_ = new GMap2(map_div, {googleBarOptions:
  {showOnLoad: true, onGenerateMarkerHtmlCallback : function(marker, html, result) {
    return me.extendMarker_(me, marker, html, result);}}});
  this.map_.setCenter(new GLatLng(37, -122));
  this.map_.addControl(new GLargeMapControl());
  this.map_.addControl(new GMapTypeControl());
  this.map_.enableGoogleBar();
  var edit_control = new EditControl();
  this.map_.addControl(edit_control);
  var status_control = new StatusControl();
  this.map_.addControl(status_control);
  GEvent.addListener(edit_control, 'view', function() { 
    me.mode_ = 'view'; 
    status_control.setText('Select geometries by clicking on them.');
  });
  GEvent.addListener(edit_control, 'point', function() { 
    me.mode_ = 'point'; 
    status_control.setText('Click on the map to create a new marker.');
  });
  GEvent.addListener(edit_control, 'line', function() { 
    me.mode_ = 'line'; 
    status_control.setText('Click on the map to start creating a new line.');
  });
  GEvent.addListener(edit_control, 'poly', function() { 
    me.mode_ = 'poly'; 
    status_control.setText('Click on the map to start creating a new filled poly.');
  });

  // Create a base icon for all of our markers that specifies the
  // shadow, icon dimensions, etc.
  var icon = new GIcon(G_DEFAULT_ICON);
  icon.image = 'http://gmaps-samples.googlecode.com/svn/trunk/markers/green/blank.png';
  icon.shadow = "http://www.google.com/mapfiles/shadow50.png";
  icon.iconSize = new GSize(20, 34);
  icon.shadowSize = new GSize(37, 34);
  icon.iconAnchor = new GPoint(9, 34);
  icon.infoWindowAnchor = new GPoint(9, 2);
  icon.infoShadowAnchor = new GPoint(18, 25);
  this.icons_ = {};
  this.icons_.unchanged = new GIcon(icon);
  this.icons_.unchanged.image = 'http://gmaps-samples.googlecode.com/svn/trunk/markers/blue/blank.png';
  this.icons_.newlysaved = new GIcon(icon);
  this.icons_.newlysaved.image = 'http://gmaps-samples.googlecode.com/svn/trunk/markers/orange/blank.png';
  this.icons_.notsaved = new GIcon(icon);
  this.icons_.notsaved.image = 'http://gmaps-samples.googlecode.com/svn/trunk/markers/red/blank.png';
  var icon = new GIcon(G_DEFAULT_ICON);
  icon.image = 'http://maps.google.com/intl/en_us/mapfiles/iw_plus.gif';
  icon.shadow = null;
  icon.iconSize = new GSize(12, 12);
  icon.shadowSize = new GSize(0, 0);
  icon.iconAnchor = new GPoint(6, 6);
  this.icons_.vertex = icon;

  GEvent.addListener(this.map_, 'click', function(overlay, latlng) {
    // todo check if we're already editing something
    if (me.mode_ == 'view' || (me.selected_geometry_ && !me.selected_geometry_.hasEnded)) {
      return;
    }
    if (overlay) return; 
    new_geometry_data = {};
    new_geometry_data.name = '';
    new_geometry_data.description = '';
    new_geometry_data.userId = current_user;
    new_geometry_data.coordinates = [];
    new_geometry_data.coordinates.push({lat: latlng.lat(), lng: latlng.lng()});
    new_geometry_data.type = me.mode_;
    var new_geometry = me.createGeometry_(new_geometry_data, true); 
    if (me.mode_ == 'point') GEvent.trigger(new_geometry, 'click');
  });
  GEvent.addListener(this.map_, 'zoomend', function() {
    me.updateHighlightPoly_();
  });
  this.loadData_();
};

geoserver.adminPanel.prototype.extendMarker_ = function(gs, marker, html, result) {
  var me = this;
  // extend the passed in html for this result
  // http://code.google.com/apis/ajaxsearch/documentation/reference.html#_class_GlocalResult

  var div = document.createElement('div');
  var button = document.createElement('input');
  button.type = 'button';
  button.value = 'Create copy on map';
  button.onclick = function() {
    var new_geometry_data = {};
    new_geometry_data.name = result.titleNoFormatting;
    new_geometry_data.description = result.streetAddress;
    new_geometry_data.userId = current_user;
    new_geometry_data.fromGoogleBar = true;
    new_geometry_data.type = 'point';
    new_geometry_data.coordinates = [];
    new_geometry_data.coordinates.push({lat: marker.getLatLng().lat(), lng: marker.getLatLng().lng()});
    marker.closeInfoWindow();
    var new_geometry = gs.createGeometry_(new_geometry_data, true); 
    GEvent.trigger(new_geometry, 'click');
  };

  div.appendChild(html);
  div.appendChild(button);
  return div;
};

geoserver.adminPanel.prototype.updateHighlightPoly_ = function() {
  var me = this;
  if (me.highlightPoly_) { me.map_.removeOverlay(me.highlightPoly_); }
  if (!me.selected_geometry_) { return; }
  if (me.selected_geometry_.data.type == 'point') {
    var latlng = me.selected_geometry_.getLatLng();
    var span = me.map_.getBounds().toSpan();
    var half_lat = span.lat() * .05;
    var half_lng = span.lng() * .05;
    var latlngs = [new GLatLng(latlng.lat() - half_lat, latlng.lng() - half_lng),
                   new GLatLng(latlng.lat() - half_lat, latlng.lng() + half_lng),
                   new GLatLng(latlng.lat() + half_lat, latlng.lng() + half_lng),
                   new GLatLng(latlng.lat() + half_lat, latlng.lng() - half_lng),
                   new GLatLng(latlng.lat() - half_lat, latlng.lng() - half_lng)];
  } else {
    if (me.selected_geometry_.isEditable && !me.selected_geometry_.hasEnded) return;
    var bounds = me.selected_geometry_.getBounds();
    var span = me.map_.getBounds().toSpan();
    var half_lat = 0;
    var half_lng = 0;
    var latlngs = [new GLatLng(bounds.getNorthEast().lat() - half_lat, bounds.getSouthWest().lng() - half_lng),
                   new GLatLng(bounds.getNorthEast().lat() - half_lat, bounds.getNorthEast().lng() + half_lng),
                   new GLatLng(bounds.getSouthWest().lat() + half_lat, bounds.getNorthEast().lng() + half_lng),
                   new GLatLng(bounds.getSouthWest().lat() + half_lat, bounds.getSouthWest().lng() - half_lng),
                   new GLatLng(bounds.getNorthEast().lat() - half_lat, bounds.getSouthWest().lng() - half_lng)];
  }
  var color = me.selected_geometry_.isEdited ? '#FF0000' : '#FF8921';
  me.highlightPoly_ = new GPolygon(latlngs, '#ff0000', 0, 0.0, color, 0.2, {clickable: false});
  me.map_.addOverlay(me.highlightPoly_);
}
    
geoserver.adminPanel.prototype.createSidebarEntry_ = function(geometry) {
  var me = this;
  var div = document.createElement('div');
  div.style.cursor = 'pointer';
  div.style.marginBottom = '5px'; 
  if (geometry.isEdited) {
    div.style.backgroundColor = '#F4BFBA';
  } else {
    div.style.backgroundColor = '#fff';
  }

  GEvent.addListener(div, 'highlight', function() {
    for (var i = 0; i < me.dom_.sidebar_divs.length; i++) {
      GEvent.trigger(me.dom_.sidebar_divs[i], 'resetview');
    } 
    me.selected_geometry_ = geometry;
    div.style.backgroundColor = '#FFD7AE';
    me.dom_.sidebar_div.scrollTop = div.offsetTop;
    me.updateHighlightPoly_();
  });

  GEvent.addDomListener(div, 'click', function() {
    if (geometry.data.userId == current_user) {
      if (div.className != 'editable_div') {
        GEvent.trigger(div, 'enableedit');
      }
    } else {
      GEvent.trigger(div, 'highlight');
    }
  });

  GEvent.addListener(div, 'dataedit', function() {
    div.style.backgroundColor = '#F4BFBA';
    //me.updateHighlightPoly_();
  });

  GEvent.addListener(div, 'resetview', function() {
    if (!geometry.isEdited) div.style.backgroundColor = '#FFf';
    div.className = 'viewable_div';
    div.innerHTML = '';
    var view_div = me.createView_(geometry, div);
    div.appendChild(view_div);

    if (geometry.data.type == 'point') {
      geometry.disableDragging();
    } else if (geometry.data.type == 'line' || geometry.data.type == 'poly') {
      geometry.disableEditing
      GEvent.clearListeners(geometry,  'mouseover');
      GEvent.clearListeners(geometry,  'mouseout');
    }
  });

  GEvent.addListener(div, 'enableedit', function() {
    for (var i = 0; i < me.dom_.sidebar_divs.length; i++) {
      GEvent.trigger(me.dom_.sidebar_divs[i], 'resetview');
    } 

    if (!geometry.isEdited) { 
      div.style.backgroundColor = '#FFD7AE';
    } else {
      div.style.backgroundColor = '#F4BFBA';
    }
    div.className = 'editable_div';
    div.innerHTML = '';
    var form_div = me.createForm_(geometry, div);
    div.appendChild(form_div);

    me.selected_geometry_ = geometry;
    me.selected_geometry_.isEditable = true;
    if (geometry.data.type == 'point') me.map_.setCenter(geometry.getLatLng());
    else me.map_.setCenter(geometry.getBounds().getCenter());
    
    me.updateHighlightPoly_();
    if (me.selected_geometry_.data.type == 'point') {
      me.selected_geometry_.enableDragging();
    }
    else if (me.selected_geometry_.data.type == 'line' || me.selected_geometry_.data.type == 'poly') {
      GEvent.addListener(geometry, 'mouseover', function() {
        //geometry.enableEditing();
      });
      GEvent.addListener(geometry, 'mouseout', function() {
        //geometry.disableEditing();
      });
    }
  });

  GEvent.trigger(div, 'resetview');
  me.dom_.sidebar_divs.push(div);
  return div;
}

geoserver.adminPanel.prototype.createTableRow_ = function(label, value, is_input, geometry) {
  var tr = document.createElement('tr');
  var label_td = document.createElement('td');
  label_td.className = 'view_label';
  label_td.appendChild(document.createTextNode(label + ': '));
  var value_td = document.createElement('td');
  if (is_input) {
    var value_input = document.createElement('input');
    value_input.type = 'text';
    value_input.value = value;
    value_input.id = label.toLowerCase() + '_input';
    value_input.onkeyup = function() {
      geometry.isEdited = true;
      GEvent.trigger(geometry.sidebar_entry, 'dataedit');
    }
    value_td.appendChild(value_input);
  } else {
    value_td.appendChild(document.createTextNode(value));
  }
  tr.appendChild(label_td);
  tr.appendChild(value_td);
  return tr;
}

geoserver.adminPanel.prototype.createView_ = function(geometry, parent_div) {
  var me = this;
 
  var div = document.createElement('div');
  div.className = 'sidebarview';
  var table = document.createElement('table');
  var tbody = document.createElement('tbody');
  tbody.appendChild(me.createTableRow_('Name', geometry.data.name, false, geometry));
  tbody.appendChild(me.createTableRow_('Description', geometry.data.description, false, geometry));
  tbody.appendChild(me.createTableRow_('Created', geometry.data.userId + ',' + geometry.data.timeStamp, false, geometry));
  table.appendChild(tbody);
  div.appendChild(table);
  if (geometry.data.userId == current_user) {
    var edit_div = document.createElement('div');
    edit_div.style.textAlign = 'center';
    var edit_button = document.createElement('input');
    edit_button.type = 'button';
    edit_button.value = 'Modify';
    edit_button.onclick = function() {
      GEvent.trigger(parent_div, 'enableedit');
    };
    edit_div.appendChild(edit_button);
    div.appendChild(edit_div);
  }
  return div;
}

geoserver.adminPanel.prototype.createForm_ = function(geometry, parent_div) {
  var me = this;

  var div = document.createElement('div');
  var table = document.createElement('table');
  var tbody = document.createElement('tbody');
  tbody.appendChild(me.createTableRow_('Name', geometry.data.name, true, geometry));
  tbody.appendChild(me.createTableRow_('Description', geometry.data.description, true, geometry));
  table.appendChild(tbody);
  div.appendChild(table);

  var save_button = document.createElement('input');
  save_button.type = 'button';
  save_button.value = 'Save';
  save_button.onclick = function() {
    me.selected_geometry_.isEditable = false;
    me.selected_geometry_.isEdited = false;
    parent_div.style.backgroundColor = '#fff';
    me.selected_geometry_.data.name = document.getElementById('name_input').value;
    me.selected_geometry_.data.description = document.getElementById('description_input').value; 
    if (me.selected_geometry_.data.type == 'point') {
      me.selected_geometry_.disableDragging();
      me.selected_geometry_.data.coordinates = [{lat: me.selected_geometry_.getLatLng().lat(), lng:  me.selected_geometry_.getLatLng().lng()}];
    } else if (me.selected_geometry_.data.type == 'line' || me.selected_geometry_.data.type == 'poly') {
      //me.selected_geometry_.disableEditing();
      GEvent.clearListeners(me.selected_geometry_,  'mouseover');
      GEvent.clearListeners(me.selected_geometry_,  'mouseout');
      me.selected_geometry_.data.coordinates = [];
      for (var i = 0; i < me.selected_geometry_.getVertexCount(); i++) {
        me.selected_geometry_.data.coordinates.push({lat: me.selected_geometry_.getVertex(i).lat(), lng: me.selected_geometry_.getVertex(i).lng()});
      }
    } 
    if (me.selected_geometry_.data.key) me.saveData_('edit', me.selected_geometry_.data);
    else me.saveData_('add', me.selected_geometry_.data); 
    GEvent.trigger(parent_div, 'resetview');
    me.selected_geometry_ = null;
    me.updateHighlightPoly_();
  }
  div.appendChild(save_button);

  var delete_button = document.createElement('input');
  delete_button.type = 'button'
  delete_button.value = 'Delete';
  delete_button.onclick = function() {
    me.saveData_('delete', me.selected_geometry_.data); 
    // should do this after delete confirmed
    if (me.selected_geometry_.data.type != 'point'){
      me.selected_geometry_.disableEditing;
    }
    me.map_.removeOverlay(me.selected_geometry_);
    me.selected_geometry_ = null;
    me.updateHighlightPoly_();
    me.dom_.sidebar_div.removeChild(parent_div);
  };
  div.appendChild(delete_button);

  var cancel_button = document.createElement('input');
  cancel_button.type = 'button';
  cancel_button.value = 'Cancel';
  cancel_button.onclick = function() {
    GEvent.trigger(parent_div, 'resetview');
    me.selected_geometry_ = null;
    me.updateHighlightPoly_();
  };
  div.appendChild(cancel_button); 
  return div;
};

geoserver.adminPanel.prototype.loadData_ = function() {
  var me = this;
  var url_base = 'gen/';
  var url = url_base + 'request?operation=get&output=json'
  GDownloadUrl(url, function(data, responseCode) { me.handleDataResponse_(me, data, responseCode); });
};

geoserver.adminPanel.prototype.saveData_ = function(type, data) {
  var url  = 'gen/request?';
  var url_params = ['operation=' + type];
  for (var data_key in data) {
    var subdata = data[data_key];
    if (subdata instanceof Array) {
      for (var i = 0; i < subdata.length; i++) {
        for (var subdata_key in subdata[i]) {
          url_params.push(subdata_key + '=' + subdata[i][subdata_key]);
        }
      }
    } else {
      url_params.push(data_key + '=' + data[data_key])
    }
  }
  //url += url_params.join('&');
  //GDownloadUrl(url, this.handleDataResponse_, url_params.join('&'));
  url += url_params.join('&');
  GDownloadUrl(url, this.handleDataResponse_);
};

geoserver.adminPanel.prototype.handleDataResponse_ = function(me, data, responseCode) {
  if (responseCode == 200) {
    var json_data = eval('(' + data + ')');
    if (json_data.status != 'success') return;
    switch (json_data.operation) {
      case 'get':
        var geometries = json_data.result.geometries;
        var bounds = new GLatLngBounds();
        for (var i = 0; i < geometries.records.length; i++) {
          var record = geometries.records[i];
          var geometry = me.createGeometry_(record);
          if (record.type == 'point') {
            bounds.extend(geometry.getLatLng());
          } else if (record.type == 'line' || record.type == 'poly') {
            bounds.extend(geometry.getBounds().getCenter());
          }  
        }
        if  (!bounds.isEmpty() && geometries.records.length > 1) {
          me.map_.setCenter(bounds.getCenter());
          me.map_.setZoom(me.map_.getBoundsZoomLevel(bounds));
        }
    }
  }
};

geoserver.adminPanel.prototype.createPoly_ = function(type, latlngs, is_editable) {
  var me = this;
  var poly = (type == 'line') ? new GPolyline(latlngs, '#ff0000', 2, 0.7,
  {clickable: false}) : new GPolygon(latlngs,
  '#0000ff', 2, 0.7, '#0000ff', 0.2, {clickable: false});
  poly.vertex_markers = [];
  for (var i = 0; i < latlngs.length; i++) {
    var marker = new GMarker(latlngs[i], {icon: me.icons_.vertex, draggable: true});
    GEvent.addListener(marker, 'dragend', function() {
      me.map_.removeOverlay(me.selected_geometry_.editable_poly);
      var latlngs = [];
      var vertex_markers = me.selected_geometry_.editable_poly.vertex_markers;
      for (var i = 0; i < vertex_markers.length; i++) {
        var latlng = vertex_markers[i].getLatLng();
        latlngs.push(latlng);
      }
      var poly = (type == 'line') ? new GPolyline(latlngs, '#ff0000', 2, 0.7,
  {clickable: false}) : new GPolygon(latlngs,
  '#0000ff', 2, 0.7, '#0000ff', 0.2, {clickable: false});
      poly.vertex_markers = vertex_markers;
      me.map_.addOverlay(poly);
      me.selected_geometry_.editable_poly = poly;
    });
    this.map_.addOverlay(marker);
    poly.vertex_markers.push(marker);
    if(!is_editable) { marker.disableDragging(); }
  }
  me.map_.addOverlay(poly);
  return poly;
}

geoserver.adminPanel.prototype.createGeometry_ = function(data, is_editable) {
  var me = this;
  if (data.type == 'point') {
    var geometry = new GMarker(new GLatLng(data.coordinates[0].lat, data.coordinates[0].lng), {draggable: true, icon: me.icons_.unchanged});
  } else if (data.type == 'line' || data.type == 'poly') {
    var latlngs = [];
    for (var i = 0; i < data.coordinates.length; i++) {
      latlngs.push(new GLatLng(data.coordinates[i].lat, data.coordinates[i].lng));
    }
    var geometry = (data.type == 'line') ? new GPolyline(latlngs, '#0000ff', 0,
    0.1) : new
    GPolygon(latlngs, '#0000ff', 0, 0.1, '#0000ff', 0.01);
    geometry.editable_poly = me.createPoly_(data.type, latlngs, is_editable);
  }
  geometry.data = data;
  if (geometry.data.userId == current_user) {
    geometry.isEdited = is_editable;
    geometry.isEditable = is_editable;
    geometry.hasEnded = !is_editable;
  }

  var sidebar_entry = me.createSidebarEntry_(geometry);
  me.dom_.sidebar_div.appendChild(sidebar_entry);
  geometry.sidebar_entry = sidebar_entry;
  if (is_editable) {
    GEvent.trigger(geometry.sidebar_entry, 'enableedit');
  }
  this.map_.addOverlay(geometry);
  this.geometries_.push(geometry);

  GEvent.addListener(geometry, 'click', function() {
    GEvent.trigger(geometry.sidebar_entry, 'highlight');
  });

  if (geometry.data.userId == current_user) { 
    if (geometry.data.type == 'point') {
      GEvent.addListener(geometry, 'click', function() {
        GEvent.trigger(geometry.sidebar_entry, 'enableedit');
      });
      GEvent.addListener(geometry, 'dragend', function() {
        geometry.isEdited = true;
        me.updateHighlightPoly_();
        GEvent.trigger(geometry.sidebar_entry, 'dataedit');
      });
    } else if (geometry.data.type == 'line' || geometry.data.type == 'poly') {
      GEvent.addListener(geometry, 'click', function() {
         console.log('enabled');
        for (var i = 0; i < geometry.editable_poly.vertex_markers.length; i++) {
          geometry.editable_poly.vertex_markers[i].enableDragging();
        }
        GEvent.trigger(geometry.sidebar_entry, 'enableedit');
      });
      GEvent.addListener(geometry, 'endline', function() {
        geometry.isEdited = true;
        geometry.hasEnded = true;
        GEvent.trigger(geometry.sidebar_entry, 'dataedit');
      });
      GEvent.addListener(geometry, 'lineupdated', function() {
        geometry.isEdited = true;
        me.updateHighlightPoly_();
        GEvent.trigger(geometry.sidebar_entry, 'dataedit');
      });
      if (is_editable) {
        me.selected_geometry_ = geometry;
        //geometry.addVerticesInteractively(); 
      }
    }
  }
  return geometry;
}
 
function StatusControl() {
}

StatusControl.prototype = new GControl();

StatusControl.prototype.initialize = function(map) {
  var me = this;
  var status_div = document.createElement('span');
  status_div.style.color = 'grey';
  status_div.style.backgroundColor = 'white';
  status_div.style.border = '1px solid grey';
  status_div.style.padding = '5px';
  status_div.innerHTML = 'Select geometries by clicking on them.';
  this.status_div = status_div;
  map.getContainer().appendChild(status_div);
  return this.status_div;
}

StatusControl.prototype.setText = function(text) {
  this.status_div.innerHTML = text;
}

StatusControl.prototype.getDefaultPosition = function() {
  return new GControlPosition(G_ANCHOR_BOTTOM_LEFT, new GSize(420, 5));
}

function EditControl() {
}

EditControl.prototype = new GControl();

EditControl.prototype.initialize = function(map) {
  var me = this;
  me.buttons_ = [];
 
  var control_div = document.createElement('div'); 
  //control_div.style.width = '100%';
  var control_table = document.createElement('table');
  //control_table.style.width = "300px";
  var control_tr = document.createElement('tr');
  
  var vc_opts = {img_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bsu.png',
                 img_hover_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bsd.png',
                 name: 'view', tooltip: 'Select geometries by clicking on them.'};
  var view_button = this.createButton_(vc_opts);
  var view_td = document.createElement('td');
  view_td.appendChild(view_button.img);

  var mc_opts = {img_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bmu.png',
                 img_hover_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bmd.png',
                 name: 'point', tooltip: 'Click on the map to create a new marker.'};
  var marker_button = this.createButton_(mc_opts);
  var marker_td = document.createElement('td');
  marker_td.appendChild(marker_button.img);

  var lc_opts = {img_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Blu.png',
                 img_hover_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bld.png',
                 name: 'line', tooltip: 'Click on the map to start creating a new line.'};
  var line_button = this.createButton_(lc_opts);
  var line_td = document.createElement('td');
  line_td.appendChild(line_button.img);

  var pc_opts = {img_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bpu.png',
                 img_hover_url: 'http://www.google.com/intl/en_us/mapfiles/ms/t/Bpd.png',
                 name: 'poly', tooltip: 'Click on the map to start creating a new filled poly.'};
  var poly_button = this.createButton_(pc_opts);
  var poly_td = document.createElement('td');
  poly_td.appendChild(poly_button.img);

  control_tr.appendChild(view_td);
  control_tr.appendChild(marker_td);
  control_tr.appendChild(line_td);
  control_tr.appendChild(poly_td);
  control_table.appendChild(control_tr);
  control_div.appendChild(control_table);
  GEvent.trigger(view_button.img, 'click');
  map.getContainer().appendChild(control_div);
  return control_div;
} 
 
EditControl.prototype.createButton_ = function(button_opts) {
  var me = this;
  var button = {};
  button.opts = button_opts;

  var button_img = document.createElement('img');
  button_img.style.cursor = 'pointer';
  button_img.width = '33';
  button_img.height = '33';
  button_img.border = '0';
  button_img.src = button_opts.img_url;
  GEvent.addDomListener(button_img, "click", function() { 
    for (var i = 0; i < me.buttons_.length; i++) {
      me.buttons_[i].img.src = me.buttons_[i].opts.img_url;
    }
    button_img.src = button_opts.img_hover_url;  
    GEvent.trigger(me, button_opts.name);
  });  

  button.img = button_img;
  me.buttons_.push(button);
  return button;
}

EditControl.prototype.getDefaultPosition = function() {
  return new GControlPosition(G_ANCHOR_BOTTOM_LEFT, new GSize(260, 0));
}
 
