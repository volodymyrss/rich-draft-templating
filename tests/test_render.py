import jinja2

def test_render():
    import ddpaper.render as render

    latex_jinja_env = render.get_latex_jinja_env()

    rendering=render.render_draft(
                        latex_jinja_env,
                        r"\VAR{test_var}",
                        {'test_var':1},
                        write_header=False,
                    )

    print("rendering",rendering)

    assert rendering == "1"

def test_render_filter():
    import ddpaper.render as render
    import ddpaper.filters as filters

    latex_jinja_env = render.get_latex_jinja_env()
    filters.setup_custom_filters(latex_jinja_env)

    rendering=render.render_draft(
                        latex_jinja_env,
                        r"\VAR{test_var|latex_exp}",
                        {'test_var':1.4123e-4},
                        write_header=False,
                    )

    print("rendering",rendering)

    assert rendering == "1.4$\\times$10$^{-4}$"

def test_render_exception():
    import ddpaper.render as render

    latex_jinja_env = render.get_latex_jinja_env()

    try:
        rendering=render.render_draft(
                            latex_jinja_env,
                            r"\BLOCK{ raise 'problem' }",
                            {'test_var':1},
                            write_header=False,
                        )
    except jinja2.exceptions.TemplateRuntimeError as e:
        assert e.args[0] == "problem"
    else:
        raise Exception("did not raise")

