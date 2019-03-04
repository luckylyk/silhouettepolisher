# Silhouette Polisher 
for Audodesk Maya 2017 (or higher)  
Author: Lionel Brouyère

### Description
This is a really simple tool to scuplt a mesh on top of a deformation chain. 
It usefull for geometry finalization and help artist to create animated corrective directly on vertexes. It works whatever the setup/rigging/deformer who drive the mesh (if the geo and the vertexe aren't locked).  
Carreful, this is not a rigging tool, this is for shot finalization.

<center>
<img src="https://raw.githubusercontent.com/luckylyk/silhouettepolisher/master/silhouettepolisher.gif" alt="drawing" align="center" width="500"/></center>

### Installation
place the "silhouettepolisher" folder the into the maya script folder.

| os       | path                                          |
| ------   | ------                                        |
| linux    | ~/< username >/maya                           |
| windows  | \Users\<username>\Documents\maya              |
| mac os x | ~<username>/Library/Preferences/Autodesk/maya |

Ensure that you pick the silhouettepolisher-master subfolder.


### How to run
```python
import silhouettepolisher
silhouettepolisher.launch()
```
