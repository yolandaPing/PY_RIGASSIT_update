# -*- coding: utf-8 -*-

# .FileName:delete_shapes.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2023/8/24 2:01
# .Finish time:
import maya.cmds as cmds
import maya.mel as mel


node = ['defaultLegacyAssetGlobals','sceneConfigurationScriptNode']
for i in node:
    try:
        cmds.select(i,r = True) 
        cmds.lockNode(lock = False) 
        cmds.delete(i) 
    except:
        pass
run = '''string $bs[] = `ls -type "blendShape"`;
for ($i in $bs) {
    if (`attributeExists "SHAPESDrivenSetGroup" $i`)
    deleteAttr -attribute "SHAPESDrivenSetGroup" $i;
    
    if (`attributeExists "SHAPESRegion" $i`)
    deleteAttr -attribute "SHAPESRegion" $i;
    
    if (`attributeExists "SHAPESData" $i`)
    deleteAttr -attribute "SHAPESData" $i;
        
        
}'''
mel.eval(run)
