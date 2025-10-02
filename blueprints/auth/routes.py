from . import auth_bp

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    ...
