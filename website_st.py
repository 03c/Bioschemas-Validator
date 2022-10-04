# Streamlit imports
import streamlit as st

# Local imports
import web.website_st_callbacks as cb
import web.report as report

# Library imports

# -------------------------------------------------------------------------
# Set site wide configuration

st.set_page_config(page_title='Bioschemas Validator',
                   page_icon='web/favicon-32x32.png',
                   layout='wide',
                   initial_sidebar_state='collapsed',
                   menu_items={
        		        'Get Help': 'https://bioschemas.org/community/',
		                'Report a bug': 'https://github.com/ElixirTeSS/bioschemas-validator/issues/',
		                'About': '# Bioschemas validation'
    		           })

hide_decoration_bar_style = '<style>header {visibility: hidden;}</style>'
#st.markdown(hide_decoration_bar_style, unsafe_allow_html=True)

# -------------------------------------------------------------------------
# Initialise session state variables

if 'metadata' not in st.session_state:
    st.session_state.metadata = ''

if 'result' not in st.session_state:
    st.session_state.result = ''

if 'result_file' not in st.session_state:
    st.session_state.result_file = ''

# -------------------------------------------------------------------------
# Page layout

# Title
logo_col, space_col, name_col = st.columns([8, 1, 100])
with logo_col:
    st.image('web/logo.png', use_column_width=True)
with name_col:
    st.title('Bioschemas Validator')

# # Introduction
with st.expander('About'):
    st.markdown('This validator is currently in beta! Help us out by raising issues on our [Github page](https://github.com/ElixirTeSS/bioschemas-validator/issues)')
# with st.expander('Help'):
#     st.markdown('more info')


# Columns
input_col, output_col = st.columns([20, 20])

with input_col:
    st.header('Please select an input method')

    st.subheader('Metadata URL')
    st.text_input('',
                  value='',
                  key='url',
                  help=None,
                  autocomplete=None,
                  on_change=cb.input_changed,
                  args=['url'],
                  kwargs=None,
                  placeholder="Enter url",
                  disabled=False)

    st.subheader('Domain or sitemap')
    st.text_input('',
                  value='',
                  key='sitemap',
                  help=None,
                  autocomplete=None,
                  on_change=cb.input_changed,
                  args=['sitemap'],
                  kwargs=None,
                  placeholder="Enter domain or sitemap",
                  disabled=False)

    st.subheader('Raw metadata')
    st.text_area('',
                 value='',
                 key='raw',
                 help=None,
                 on_change=cb.input_changed,
                 args=['raw'],
                 kwargs=None,
                 placeholder='Paste metadata here',
                 disabled=False
                 )

with output_col:
    st.header("Validation report")

    if st.session_state.result != '':
        result = st.session_state.result  # local alias

        # File Download
        st.download_button('Download Report', st.session_state.result_file)

        # Report summary
        markdown_text = report.generate_report_summary(result)
        st.markdown(markdown_text, unsafe_allow_html=True)

        report_dataframe = report.get_dataframe(result)
        st.dataframe(report_dataframe)

        # Report body
        markdown_text = report.generate_report_body(result)
        st.markdown(markdown_text, unsafe_allow_html=True)

    # Debug
    # if st.session_state.result != '':
    #     st.write(st.session_state.result)
    #     st.text(st.session_state.result_file)
