# Developing `Develop Activity`
## Ninja-IDE
Ninja IDE is a direct dependency of `develop-activity`, 
Ninja IDE is obtained from https://github.com/ninja-ide/ninja-ide 
Ninja releases new introspection libraries which is used by develop activity to check the code.

### Porting Ninja IDE
Ninja IDE comes bundled with its original GUI, its tests, installer etc. However these are unnecessary. 
Moreover, Ninja IDE Python3 branch is still in beta. So there are bugs in the code.
For temporary fixes and removing code, there are patches on https://github.com/srevinsaju/ninja-ide/tree/minima

The porting, or fixes are provided in patches, referred to in the folder 
https://github.com/srevinsaju/ninja-ide/tree/minima/patch-20191229
Apply each patch to the latest Ninja-IDE version, so that the app is compatible, as well as we
reduce the size of the develop-activity without adding unused dependencies.

### Additional Notes
Ninja IDE is a very old repository with a lot of commits
After cloning the latest repository and applying the patches mentioned above, 
consider removing `.git`, `.gitignore` to further reduce the size
and to prevent internal conflicts
