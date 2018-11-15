==================
Serpyco benchmarks
==================

From `<https://github.com/voidfiles/python-serialization-benchmark>`_:

===================== ====================== ==================== ========
Library               Many Objects (seconds) One Object (seconds) Relative
===================== ====================== ==================== ========
Serpyco                           0.00618839           0.00304437  1
Custom                            0.00659513           0.0038712   1.13361
lima                              0.00792766           0.00405002  1.2973
serpy                             0.0237653            0.0117433   3.84594
Strainer                          0.0360789            0.0200641   6.08085
Toasted Marshmallow               0.0430918            0.023999    7.2666
Colander                          0.136315             0.0678208   22.11
Lollipop                          0.214421             0.102774    34.3554
Marshmallow                       0.305463             0.157168    50.1075
kim                               0.38243              0.195495    62.595
Django REST Framework             0.470731             0.328495    86.5641
===================== ====================== ==================== ========

Ran on a Intel Core i5-6500 CPU, Python 3.7.1 on Debian Stretch.