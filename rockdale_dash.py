import streamlit as st
from PIL import Image
import pandas as pd
import geopandas as gpd
import plotly.express as px
import pydeck as pdk

# set global variables
county_var = 'Rockdale'
latitude = 33.66
longitude_2D = -84.04
longitude_3D = -83.54
min_zoom = 8
max_zoom = 15
zoom_2D = 10  # lower values zoom out, higher values zoom in
zoom_3D = 8.5
map_height = 565

# set choropleth colors for the map
custom_colors = [
    '#97a3ab',  # lightest blue
    '#667883',
    '#37505d',
    '#022b3a'  # darkest blue
]

# convert the above hex list to RGB values
custom_colors = [tuple(int(h.lstrip('#')[i:i+2], 16)
                       for i in (0, 2, 4)) for h in custom_colors]

# set page configurations
st.set_page_config(
    page_title=f"{county_var} County Housing Trends",
    page_icon=":house:",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# the custom CSS lives here:
hide_default_format = """
        <style>
            .reportview-container .main footer {visibility: hidden;}    
            #MainMenu, footer {visibility: hidden;}
            section.main > div:has(~ footer ) {
                padding-bottom: 1px;
                padding-left: 40px;
                padding-right: 40px;
                padding-top: 50px;
            }
            [data-testid="stSidebar"] {
                padding-left: 18px;
                padding-right: 18px;
                padding-top: 0px;
                }
            [data-testid="collapsedControl"] {
                color: #FFFFFF;
                background-color: #022B3A;
                } 
            span[data-baseweb="tag"] {
                background-color: #022B3A 
                }
            div.stActionButton{visibility: hidden;}
        </style>
       """

# inject the CSS
st.markdown(hide_default_format, unsafe_allow_html=True)

# sidebarvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

# Title of dashboard radio button for housing variable
st.sidebar.markdown(
    f"<p style='text-align:center;color:#FFFFFF;font-style:italic;'>View housing data by:</p>", unsafe_allow_html=True)

# Radio buttons for selecting the housing dashboard variable
dash_variable = st.sidebar.radio(
    label='',
    options=('Total sales', 'Price (per SF)', 'Price (overall)'),
    index=1,
    label_visibility='collapsed'
)

# dictionary for converting housing dashboard variables into actionable values
dash_variable_dict = {
    'Total sales': ['yr_built', 'count', '{:,.0f}'],
    'Price (per SF)': ['price_sf', 'median', '${:.2f}'],
    'Price (overall)': ['sale_price', 'median', '${:,.0f}']
}

# # Sidebar divider #1
st.sidebar.write("---")

# Allow user to filter data
st.sidebar.markdown(
    f"<p style='text-align:center;color:#FFFFFF;font-style:italic;'>Filter housing data by:</p>", unsafe_allow_html=True)

# Transaction year sidebar slider
years = st.sidebar.select_slider(
    'Transaction year',
    options=[
        2018,
        2019,
        2020,
        2021,
        2022,
        2023
    ],
    value=(2021, 2023)
)

# dashboard main title styling variables
dash_title1_color = '#FFFFFF'
dash_title_font_size = '20'
dash_title1_font_weight = '900'
line_height1 = '12'

# dashboard year title styling variables (e.g., '2021 - 2023')
dash_title2_color = '#022B3A'
dash_title2_font_weight = '600'
line_height2 = '5'

# construct dashboard main title
if years[0] != years[1]:
    st.markdown(
        f"<h2 style='color:{dash_title1_color}; font-weight: {dash_title1_font_weight};'>{county_var} County Housing Trends | <span style='color:{dash_title2_color}; font-weight: {dash_title2_font_weight}'>{years[0]} - {years[1]}</span></h2>", unsafe_allow_html=True)
else:
    st.markdown(
        f"<h2 style='color:{dash_title1_color}; font-weight: {dash_title1_font_weight};'>{county_var} County Housing Trends | <span style='color:{dash_title2_color}; font-weight: {dash_title2_font_weight}'>{years[0]} only</span></h2>", unsafe_allow_html=True)

# construction vintage slider
year_built = st.sidebar.select_slider(
    'Year built',
    options=['<2000', '2000-2010', '2011-2023'],
    value=('<2000', '2011-2023')
)

# dictionary for filtering by construction vintage
year_built_dict = {
    '<2000': [0, 1999],
    '2000-2010': [2000, 2010],
    '2011-2023': [2011, 2050]
}

# sub-geography slider
geography_included = st.sidebar.radio(
    'Geography included',
    ('Entire county', 'City/Region'),
    index=0,
    help='Filter sales by location. Defaults to entire county. "City/Region" filter will allow multi-select of smaller groupings within the county.'
)

# sub-geography options
sub_geos_list = [
    'Conyers',
    'North Rockdale',
    'South Rockdale'
]

# Logic & select box for the sub-geographies
sub_geo = ""
if geography_included == 'City/Region':
    sub_geo = st.sidebar.multiselect(
        'Select one or more cities/regions:',
        sub_geos_list,
        ['Conyers'],
    )

# Sidebar divider #2
st.sidebar.write("---")

# Map options for 2D / 3D & basemap
st.sidebar.markdown(
    f"<p style='text-align:center; color:#FFFFFF; font-style:italic; line-height:2px'>Additional map options:</p>", unsafe_allow_html=True)

# Toggle from 2D to 3D, but only if the dashboard variable is either price / SF or price (overall)
if dash_variable == 'Price (per SF)' or dash_variable == 'Price (overall)':
    map_view = st.sidebar.radio(
        'Map view',
        ('2D', '3D'),
        index=0,
        horizontal=True,
        help='Toggle 3D view to extrude map polygons showing "height" based on total number of home sales for the selected filters. Darker map colors correspond to higher median sales price / SF.'
    )
else:
    map_view = st.write('')

# dropdown to select the basemap
base_map = st.sidebar.selectbox(
    'Base map',
    ('Streets', 'Satellite', 'Gray'),
    index=2,
    help='Change underlying base map.'
)

# dictionary to change the basemap
base_map_dict = {
    'Streets': 'road',
    'Satellite': 'satellite',
    'Gray': 'light'
}

# sidebar^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


@st.cache_data
def load_tab_data():
    # load the data
    df = pd.read_csv(
        'Geocode/RockdaleJoined_18-23.csv',
        thousands=',',
        keep_default_na=False
    )

    # drop Unnamed column, if it exists
    if any(df.columns.str.startswith('Unnamed')):
        df = df.loc[:, ~df.columns.str.startswith('Unnamed')]

    # # create 'unique' field
    # df['unique_ID'] = df['Parcel ID'].astype(
    #     str) + '-' + df['sale_date'] + '-' + df['sale_price'].astype(str)

    # Drop the unneeded columns
    df.drop(
        ['Parcel ID', 'Address', 'lat', 'long', 'geometry'],
        axis=1,
        inplace=True)

    # return this item
    return df


# initialize the dataframe by running this cached function
df_init = load_tab_data()


# function to filter data for the map (by year, vintage, sub_geo) & then groupby
def filter_data_map():

    # read in dataframe
    df = df_init

    # get transaction year lower / upper bounds
    year_lower_bound = years[0]
    year_upper_bound = years[1]

    # get construction vintage lower / upper bounds
    vintage_lower_bound = year_built_dict[year_built[0]][0]
    vintage_upper_bound = year_built_dict[year_built[1]][1]

    # Now apply filters based on transaction year, construction vintage, and sub-geography (if applicable)
    if geography_included == 'City/Region':  # apply a sub-geography filter
        filtered_df = df[
            (df['year'] >= year_lower_bound) &
            (df['year'] <= year_upper_bound) &
            (df['yr_built'] >= vintage_lower_bound) &
            (df['yr_built'] <= vintage_upper_bound) &
            (df['Sub_geo'].isin(sub_geo))]
    else:  # do not apply a sub-geography filter
        filtered_df = df[
            (df['year'] >= year_lower_bound) &
            (df['year'] <= year_upper_bound) &
            (df['yr_built'] >= vintage_lower_bound) &
            (df['yr_built'] <= vintage_upper_bound)
        ]

    # now group by GEOID, i.e. Census tract
    grouped_df = filtered_df.groupby('GEOID').agg({
        # this first agg will read the dash variable and make the correct calculation
        dash_variable_dict[dash_variable][0]: dash_variable_dict[dash_variable][1],

        # this second agg will get the name of the sub geometry for each Census tract
        'Sub_geo': pd.Series.mode
    }).reset_index()

    return filtered_df, grouped_df


# fire the function above to filter down the data, but not to group it, for the KPIs
kpi_df = filter_data_map()[0]

# calculate & format all necessary KPI values from the filtered data
median_sf = '{:,.0f}'.format(kpi_df['square_feet'].median())
median_vintage = '{:.0f}'.format(kpi_df['yr_built'].median())
total_sales = '{:,.0f}'.format(kpi_df.shape[0])
median_price = '${:,.0f}'.format(kpi_df['sale_price'].median())
median_price_sf = '${:.0f}'.format(kpi_df['price_sf'].median())

# calculate variables from the filtered dataframe that will drive the YoY change KPIs
df_firstYear = kpi_df[kpi_df['year'] == years[0]]
df_secondYear = kpi_df[kpi_df['year'] == years[1]]
delta_total_sales = '{:.1%}'.format((df_secondYear['price_sf'].count() -
                                     df_firstYear['price_sf'].count()) / df_firstYear['price_sf'].count())
delta_price_sf = '{:.1%}'.format((df_secondYear['price_sf'].median() -
                                  df_firstYear['price_sf'].median()) / df_firstYear['price_sf'].median())
delta_price = '{:.2%}'.format((df_secondYear['sale_price'].median() -
                               df_firstYear['sale_price'].median()) / df_firstYear['sale_price'].median())


# # colors to be used in the mapping functions
# custom_colors = [
#     '#97a3ab',  # lightest blue
#     '#667883',
#     '#37505d',
#     '#022b3a'  # darkest blue
# ]

# # convert the above hex list to RGB values
# custom_colors = [tuple(int(h.lstrip('#')[i:i+2], 16)
#    for i in (0, 2, 4)) for h in custom_colors]


def mapper_2D():

    # tabular data
    df = filter_data_map()[1]
    df['GEOID'] = df['GEOID'].astype(str)

    # read in geospatial
    gdf = gpd.read_file('Geography/Rockdale_CTs.gpkg')

    # join together the 2, and let not man put asunder
    joined_df = gdf.merge(df, left_on='GEOID', right_on='GEOID')

    # ensure we're working with a geodataframe
    joined_df = gpd.GeoDataFrame(joined_df)

    # gonna be ugly as sin, but format the proper column
    joined_df['var_formatted'] = joined_df[dash_variable_dict[dash_variable][0]].apply(
        lambda x: dash_variable_dict[dash_variable][2].format((x)))

    # create a 'label' column
    joined_df['dashboard_var_label'] = dash_variable

    # set choropleth color
    joined_df['choro_color'] = pd.cut(
        joined_df[dash_variable_dict[dash_variable][0]],
        bins=len(custom_colors),
        labels=custom_colors,
        include_lowest=True,
        duplicates='drop'
    )

    # st.write(joined_df.columns)
    # st.write(dash_variable_dict[dash_variable][0])
    # st.write(joined_df['var_formatted'][0])
    # st.write(joined_df['choro_color'][1])

    # create map intitial state
    initial_view_state = pdk.ViewState(
        latitude=latitude,
        longitude=longitude_2D,
        zoom=zoom_2D,
        max_zoom=max_zoom,
        min_zoom=min_zoom,
        pitch=0,
        bearing=0,
        height=map_height
    )

    geojson = pdk.Layer(
        "GeoJsonLayer",
        joined_df,
        pickable=True,
        autoHighlight=True,
        highlight_color=[255, 255, 255, 80],
        opacity=0.5,
        stroked=True,
        filled=True,
        get_fill_color='choro_color',
        get_line_color=[0, 0, 0, 255],
        line_width_min_pixels=1
    )

    tooltip = {
        "html": "{dashboard_var_label}: <b>{var_formatted}</b><hr style='margin: 10px auto; opacity:0.5; border-top: 2px solid white; width:85%'>\
                    Census Tract {GEOID} <br>\
                    {Sub_geo}",
        "style": {"background": "rgba(2,43,58,0.7)",
                  "border": "1px solid white",
                  "color": "white",
                  "font-family": "Helvetica",
                  "text-align": "center"
                  },
    }

    r = pdk.Deck(
        layers=geojson,
        initial_view_state=initial_view_state,
        map_provider='mapbox',
        map_style=base_map_dict[base_map],
        tooltip=tooltip)

    return r


st.pydeck_chart(mapper_2D(), use_container_width=True)

# def mapper_3D():

#     # tabular data
#     df = filter_data()[1]
#     df['GEOID'] = df['GEOID'].astype(str)

#     # read in geospatial
#     gdf = gpd.read_file('Geography/Forsyth_CTs.gpkg')

#     # join together the 2, and let not man put asunder
#     joined_df = gdf.merge(df, left_on='GEOID', right_on='GEOID')

#     # ensure we're working with a geodataframe
#     joined_df = gpd.GeoDataFrame(joined_df)

#     # format the column to show the price / SF
#     joined_df['price_sf_formatted'] = joined_df['price_sf'].apply(
#         lambda x: "${:.0f}".format((x)))

#     # add 1,000 separator to column that will show total sales
#     joined_df['total_sales'] = joined_df['unique_ID'].apply(
#         lambda x: '{:,}'.format(x))

#     # set choropleth color
#     joined_df['choro_color'] = pd.cut(
#         joined_df['price_sf'],
#         bins=len(custom_colors),
#         labels=custom_colors,
#         include_lowest=True,
#         duplicates='drop'
#     )

#     # set initial view state
#     initial_view_state = pdk.ViewState(
#         latitude=34.307054643497315,
#         longitude=-84.10535919531371,
#         zoom=9.2,
#         max_zoom=15,
#         min_zoom=8,
#         pitch=45,
#         bearing=0,
#         height=565
#     )

#     # create geojson layer
#     geojson = pdk.Layer(
#         "GeoJsonLayer",
#         joined_df,
#         pickable=True,
#         autoHighlight=True,
#         highlight_color=[255, 255, 255, 90],
#         opacity=0.5,
#         stroked=False,
#         filled=True,
#         wireframe=False,
#         extruded=True,
#         get_elevation='unique_ID * 50',
#         get_fill_color='choro_color',
#         get_line_color='choro_color',
#         line_width_min_pixels=1
#     )

#     tooltip = {
#         "html": "Median price per SF: <b>{price_sf_formatted}</b><br>Total sales: <b>{total_sales}</b>",
#         "style": {"background": "rgba(2,43,58,0.7)",
#                   "border": "1px solid white",
#                   "color": "white",
#                   "font-family": "Helvetica",
#                   "text-align": "center"
#                   },
#     }

#     r = pdk.Deck(
#         layers=geojson,
#         initial_view_state=initial_view_state,
#         map_provider='mapbox',
#         map_style=base_map_dict[base_map],
#         tooltip=tooltip)

#     return r


# def charter():
#     # test chart
#     df = filter_data()[0]

#     df_grouped = df.groupby('year-month').agg({
#         'price_sf': 'median',
#         'unique_ID': 'count',
#         'month': pd.Series.mode,
#         'year': pd.Series.mode,
#     }).reset_index()

#     # sort the data so that it's chronological
#     df_grouped = df_grouped.sort_values(['year', 'month'])

#     fig = px.line(
#         df_grouped,
#         x="year-month",
#         y='price_sf',
#         custom_data=['unique_ID']
#     )

#     # modify the line itself
#     fig.update_traces(
#         mode="lines",
#         line_color='#022B3A',
#         hovertemplate="<br>".join([
#             # "<b>%{x}</b><br>",
#             "Median price / SF: <b>%{y}</b>",
#             "Total sales: <b>%{customdata[0]:,.0f}</b>"
#         ])
#     )

#     # set chart title style variables
#     chart_title_font_size = '17'
#     chart_title_color = '#FFFFFF'
#     chart_title_font_weight = '650'

#     chart_subtitle_font_size = '14'
#     chart_subtitle_color = '#022B3A'
#     chart_subtitle_font_weight = '650'

#     if sub_geo == "":
#         chart_title_text = "Countywide Median Price / SF"
#     elif len(sub_geo) == 1:
#         chart_title_text = f"{sub_geo[0]} Median Price / SF"
#     elif len(sub_geo) == 2:
#         chart_title_text = f"{sub_geo[0]} & {sub_geo[1]} Median Price / SF"
#     else:
#         chart_title_text = f"Median Price / SF For Selected Regions"

#     # update the fig
#     fig.update_layout(
#         title_text=f'<span style="font-size:{chart_title_font_size}px; font-weight:{chart_title_font_weight}; color:{chart_title_color}">{chart_title_text}</span><br><span style="font-size:{chart_subtitle_font_size}px; font-weight:{chart_subtitle_font_weight}; color:{chart_subtitle_color}"><i>Orange lines reflect range of selected years</i></span>',
#         title_x=0,
#         title_y=0.93,
#         margin=dict(
#             t=85
#         ),
#         hoverlabel=dict(
#             bgcolor="rgba(255, 255, 255, 0.8)",
#             bordercolor="#022B3A",
#             font_size=16,  # set the font size of the chart tooltip
#             font_color="#022B3A",
#             align="left"
#         ),
#         yaxis=dict(
#             linecolor="#022B3A",
#             title=None,
#             tickfont_color='#022B3A',
#             tickfont_size=13,
#             tickformat='$.0f',
#             showgrid=False
#         ),
#         xaxis=dict(
#             linecolor="#022B3A",
#             linewidth=1,
#             tickfont_color='#022B3A',
#             title=None,
#             tickangle=90,
#             tickfont_size=13,
#             tickformat='%b %Y',
#             dtick='M3'
#         ),
#         height=460,
#         hovermode="x unified")

#     # add shifting vertical lines
#     year_start = {
#         2018: '2018-1',
#         2019: '2019-1',
#         2020: '2020-1',
#         2021: '2021-1',
#         2022: '2022-1',
#         2023: '2023-1'
#     }

#     year_end = {
#         2018: '2018-12',
#         2019: '2019-12',
#         2020: '2020-12',
#         2021: '2021-12',
#         2022: '2022-12',
#         2023: '2023-4'
#     }

#     fig.add_vline(x=year_start[years[0]], line_width=2,
#                   line_dash="dash", line_color="#FF8966")
#     fig.add_vline(x=year_end[years[1]], line_width=2,
#                   line_dash="dash", line_color="#FF8966")

#     return fig


# define columns for the first "row" of map, KPIs, and chart
col1, col2, col3 = st.columns([
    2.5,  # map column
    0.2,  # spacer column
    3  # KPI / chart column
])


# if map_view == '2D':
#     col1.pydeck_chart(mapper_2D(), use_container_width=True)
# else:
#     col1.pydeck_chart(mapper_3D(), use_container_width=True)

# # kpi values
# total_sales = '{:,.0f}'.format(filter_data()[1]['unique_ID'].sum())
# median_price_SF = '${:.0f}'.format(filter_data()[2]['price_sf'].median())
# median_price = '${:,.0f}'.format(filter_data()[2]['Sale Price'].median())
# med_vintage = '{:.0f}'.format(filter_data()[2]['year_blt'].median())
# med_SF = '{:,.0f}'.format(filter_data()[2]['Square Ft'].median())
# YoY_delta = '{0:.1%}'.format((filter_data()[4]['price_sf'].median(
# ) - filter_data()[3]['price_sf'].median()) / filter_data()[3]['price_sf'].median())

# # kpi styles
# KPI_label_font_size = '15'
# KPI_label_font_color = '#FFFFFF'
# KPI_label_font_weight = '700'  # thickness of the bold

# KPI_value_font_size = '25'
# KPI_value_font_color = '#022B3A'
# KPI_value_font_weight = '800'  # thickness of the bold

# KPI_line_height = '25'  # vertical spacing between the KPI label and value


# # KPI tyme
# with col3:
#     subcol1, subcol2, subcol3, subcol4 = st.columns([1, 1, 1, 1])

#     # first metric - "Total sales"
#     subcol1.markdown(f"<span style='color:{KPI_label_font_color}; font-size:{KPI_label_font_size}px; font-weight:{KPI_label_font_weight}'>Total home sales</span><br><span style='color:{KPI_value_font_color}; font-size:{KPI_value_font_size}px; font-weight:{KPI_value_font_weight}; line-height: {KPI_line_height}px'>{total_sales}</span>", unsafe_allow_html=True)

#     # second metric - "Median price"
#     subcol2.markdown(f"<span style='color:{KPI_label_font_color}; font-size:{KPI_label_font_size}px; font-weight:{KPI_label_font_weight}'>Median sale price</span><br><span style='color:{KPI_value_font_color}; font-size:{KPI_value_font_size}px; font-weight:{KPI_value_font_weight}; line-height: {KPI_line_height}px'>{median_price}</span>", unsafe_allow_html=True)

#     # third metric - "Median vintage"
#     subcol3.markdown(f"<span style='color:{KPI_label_font_color}; font-size:{KPI_label_font_size}px; font-weight:{KPI_label_font_weight}'>Median vintage</span><br><span style='color:{KPI_value_font_color}; font-size:{KPI_value_font_size}px; font-weight:{KPI_value_font_weight}; line-height: {KPI_line_height}px'>{med_vintage}</span>", unsafe_allow_html=True)

#     # fourth metric - "Median SF"
#     subcol4.markdown(f"<span style='color:{KPI_label_font_color}; font-size:{KPI_label_font_size}px; font-weight:{KPI_label_font_weight}'>Median size (SF)</span><br><span style='color:{KPI_value_font_color}; font-size:{KPI_value_font_size}px; font-weight:{KPI_value_font_weight}; line-height: {KPI_line_height}px'>{med_SF}</span>", unsafe_allow_html=True)

#     # delta KPI, resting under the 4 KPIs above
#     if years[0] != years[1]:
#         col3.markdown(
#             f"<span style='color:{KPI_label_font_color}; font-size: 17px; font-weight:{KPI_label_font_weight}; display: flex; justify-content: center; white-space:nowrap;'>Change in median price / SF from {years[0]} to {years[1]}: </span><span style='color:{KPI_value_font_color}; font-size: 25px; font-weight:{KPI_label_font_weight}; display:flex; justify-content:center; line-height:20px'>{YoY_delta} </span>", unsafe_allow_html=True)
#     else:
#         col3.markdown(
#             f"<span style='color:{KPI_label_font_color}; font-size: 17px; font-weight:{KPI_label_font_weight}; display: flex; justify-content: center;'>No year over year change.</span>", unsafe_allow_html=True)


# # draw the plotly line chart
# col3.plotly_chart(charter(), use_container_width=True, config={
#                   'displayModeBar': False}, help='test')

# define columns for the second "row" of notes & logo
col1, col2 = st.columns([
    2,    # expander notes column
    1     # logo column
])

# put expander explanatory text
if map_view == '2D':
    with col1:
        expander = st.expander("Notes")
        expander.markdown(
            f"<span style='color:#022B3A'> Darker shades of Census tracts represent higher sales prices per SF for the selected time period. Dashboard excludes non-qualified, non-market, and bulk transactions. Excludes transactions below $1,000 and homes smaller than 75 square feet. Data downloaded from {county_var} County public records on September 15, 2023.</span>", unsafe_allow_html=True)
else:
    with col1:
        col1.markdown("<span style='color:#022B3A'><b>Shift + click</b> in 3D view to rotate and change map angle. Census tract 'height' represents total sales. Darker colors represent higher median sales price / SF.</span>", unsafe_allow_html=True)
        expander = st.expander("Notes")
        expander.markdown(
            f"<span style='color:#022B3A'>Census tract 'height' representative of total sales per tract. Darker shades of Census tracts represent higher sales prices per SF for the selected time period. Dashboard excludes non-qualified, non-market, and bulk transactions. Excludes transactions below $1,000 and homes smaller than 75 square feet. Data downloaded from {county_var} County public records on September 15, 2023.</span>", unsafe_allow_html=True)

# Draw ARC logo at the bottom of the page
im = Image.open('Content/logo.png')
with col2:
    subcol1, subcol2, subcol3 = st.columns([1, 1, 1])
    # with subcol
    subcol2.write("Powered by:")
    subcol3.image(im, width=80)
