print(
    serializer.load(
        {"color": 1, "points": [{"x": 1, "y": 2}, {"x": 2, "y": 3}, {"x": 4, "y": 5}]}
    )
)
Polygon(
    points=[Point(x=1, y=2), Point(x=2, y=3), Point(x=4, y=5)],
    color=PolygonColor.RED,
    name=None,
)
