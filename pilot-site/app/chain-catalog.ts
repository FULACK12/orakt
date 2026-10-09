import {hormuzChain} from './hormuz-network.mjs';
import {pathGeometry} from './map-path-geometry.mjs';
export {hormuzChain};
export function chainGeoJSON(){return pathGeometry([hormuzChain],['hormuz-helium'],'zh');}
