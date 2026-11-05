SetFactory("OpenCASCADE");
Cone(1) = {0,0,0, 0,0,0.12, 0.03, 0.039};
Physical Volume("internal") = {1};
Physical Surface("inlet") = {1};
Physical Surface("walls") = {2};
Physical Surface("outlet") = {3};
Mesh.CharacteristicLengthMax = 0.005;
Mesh.CharacteristicLengthMin = 0.005;
Mesh.Optimize = 1;
