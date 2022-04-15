from cgitb import html
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS, cross_origin
import requests
from bs4 import BeautifulSoup as bs
from urllib.request import urlopen as uReq
import json ###Details of the courses are going to be json
## To Scrap sub categories of website as loading of courses happens when we scroll down
from selenium import webdriver 
from selenium.webdriver.common.by import By
import time
import pymongo
import logging
import datetime
### Initiating functions
app= Flask(__name__)
ineuron_url="https://courses.ineuron.ai/"
## Initiating logging with parameters
log_file= 'divisible_by_zero_'+str(datetime.datetime.now())+'.log'
logging.basicConfig(filename=log_file, 
                   level= logging.DEBUG,
                   format=("%(asctime)s %(levelname)s %(message)s"))
logging.info("Start of logging")

@app.route('/',methods=['GET'])  # route to display the home page
@cross_origin()
def homePage():
    return render_template("index.html")


'''Consists of all the methods to retrieve course details'''
class ineuron_Course():
    def __init__(self,ineuron_url,dbclient, dbname,dbcollectionname):
        self.ineuron_url= ineuron_url
        self.dbclient= dbclient
        self.dbname= dbname
        self.dbcollectionname= dbcollectionname
        ##self.ineuron_url_head= ineuron_url_head
        '''
        self.csv_file=open('Course_details.csv',"w")
        self.header="Course category,Course Name,Course Url \n"
        self.csv_file.write(self.header)'''
    '''Generates the details of course categories'''
    def getCourseCategory(self):
        ### navigating to ineuron courses page
        try:
            ineuron_courses= uReq(self.ineuron_url)
            ineuron_courses_html= ineuron_courses.read()
            ineuron_courses.close()
        except Exception as e:
            print("The Exception message:",e)
            logging.error("Exception raised: "+ str(e))

            #return "Could not able to navigate or read url"

        ## Beautifying html
        ineuron_courses_beautify=bs(ineuron_courses_html, "html.parser")
        ### Parse to respective tags
        try:
            ineuron_course_tag= ineuron_courses_beautify.find_all("script", {'id':'__NEXT_DATA__'})[0]
            ### Converting list iterator to list followed by string
            ineuron_course_string= list(ineuron_course_tag.children)[0]
        except Exception as e:
            print("Tag not available:",e)
            #print("Exception occured:",e)
            logging.error("Exception raised: "+ str(e))

        try:
            ##Conversion of string to json format
            ineuron_courses_json= json.loads(ineuron_course_string)
        except Exception as e:
            print("Json loading failed:", e)
            logging.error("Exception raised: "+ str(e))

        ### Getting the categories from json file
        ineuron_course_categories= ineuron_courses_json['props']['pageProps']['initialState']['init']['categories']

        ### printing course urls
        for course_cat in ineuron_course_categories.values():
            ineuron_course_subcategory= course_cat['subCategories']
            self.course_category_title= course_cat['title']
            for course_subcat in ineuron_course_subcategory.values():
                yield self.ineuron_url+'category/'+course_subcat['title'].replace(" ", "-")
    '''Navigating to the respective url and scrolling down'''
    def pageNavigateAndScroll(self, navigation_url, driver, sleep_time: int =1):
        driver.get(navigation_url)
        page_bottom=0

        while True:
            driver.execute_script("window.scrollTo(500, document.body.scrollHeight);")
            time.sleep(sleep_time)
            scroll_down_height=driver.execute_script("return document.body.scrollHeight")
            if scroll_down_height==page_bottom:
                break
            else:
                page_bottom= scroll_down_height
        return driver
        ###After scrolling getting the tags and converting them to html




    '''getting all the details of course for each course category'''
    def getCourses(self, wb: webdriver, browser_path, driver_path, sleep_time=1):
        '''Creating Db connection with mongodb and inserting data into document'''
        course_cat_document= self.dbConnection()
        
        ###Looping around category urls and getting all the course details
        for course_category_url in self.getCourseCategory():
            try:
                ###Scrapping Course category url with web driver
                chrome_browserless_option= wb.ChromeOptions()
                ## Passing browser path, Note: This should be enabled when running in Cloud (eg: Heroku)
                chrome_browserless_option.binary_location = browser_path
                ## Headless will processdata without opening browser
                chrome_browserless_option.add_argument('headless')
                ##Getting Chromedriver extension
                driver= wb.Chrome(executable_path=driver_path, options= chrome_browserless_option)
                ##driver= wb.Chrome(executable_path=driver_path) ## For browser option
            except Exception as e:
                print("Failed to open browser, Please check browser options")
                print("Error Details:",e)
                logging.error("Exception raised: "+ str(e))
            ##Navigating to Url
            html_driver= self.pageNavigateAndScroll(course_category_url, driver,sleep_time)
            ##print(type(html_driver))

            ### Getting Url attributes and converting to html
            try:
                inner_html= html_driver.find_element(by= By.CLASS_NAME, value= "AllCourses_course-list__36-kz").get_attribute("innerHTML")
            except:
                ### When tag is un-available then skip the url and continue
                continue

            ##Parsing using Bs
            html_parser= bs(inner_html,'html.parser')

            ### Getting the tags and find the url attributes
            tags_with_a= html_parser.div.div.find_all('a')

            ## Loop the tags with a and getting href attributes
            for href in tags_with_a:
                try:
                    course_extended_url= href.attrs['href']
                    course_name=href.get_text()
                except Exception as e:
                    print("Href attribute not available")
                    print("Error details:",e)
                    logging.error("Exception raised: "+ str(e))
                '''Writing to file
                course_csv_file_data=self.course_category_title
                course_csv_file_data+=','
                course_csv_file_data+=course_name
                course_csv_file_data+=','
                course_det_url=self.ineuron_url.rstrip("/")+course_extended_url
                course_csv_file_data+=course_det_url
                course_csv_file_data+='\n' '''
                course_det_url=self.ineuron_url.rstrip("/")+course_extended_url
                #self.csv_file.write(course_csv_file_data)
                ##print(self.ineuron_url.rstrip("/")+course_extended_url)
                '''inserting data into document'''
                course_details_row=self.readCourseDetails(course_det_url, self.course_category_title)
                try:
                    course_cat_document.insert_one(course_details_row)
                except Exception as e:
                    print("Insertion failed, Please re-verify collection details")
                    print("Error details",e)
                    logging.error("Exception raised: "+ str(e))
                #print(course_details_row['_id'])

            break    
        #self.csv_file.close()

            
    '''Navigating to the courses and reading the data'''
    def readCourseDetails(self, course_url, course_category):
        ###Navigating to the location and reading the data
        course_urlib=uReq(course_url)
        course_urlib_html=course_urlib.read()
        course_urlib.close()

        ## Beautify
        course_details_parse= bs(course_urlib_html, "html.parser")
        #course_details_parse=course_urlib_html.prettify()
        try:
            ### Parsing the tag and loading the course details data in json format
            for i in course_details_parse.find_all("script", {"id":"__NEXT_DATA__"})[0]:
                course_details=json.loads(i)
            
            '''Getting all the course details into Dict to load into db'''

            ### Course ID
            collection_course_id= course_details['props']['pageProps']['data'].get('_id')

            ## Course Category: Taken from the parameters
            ## Course Url: Taken from the parameters

            ## Course Title
            collection_course_title= course_details['props']['pageProps']['data'].get('title')

            ## Course Description
            collection_course_description= course_details['props']['pageProps']['data']['details'].get('description')

            ##Course Mode
            collection_course_mode= course_details['props']['pageProps']['data']['details'].get('mode')

            ## Course Batch details
            course_batches={}
            if collection_course_mode=='live':
                ### live bathches has seperate tag with batches and id for that, we are converting batches to list
                #### then adding tag meta and curriculum to get the details
                course_batches=list(course_details['props']['pageProps']['data']['batches'].values())[0]['meta']
            else:
                course_batches=course_details['props']['pageProps']['data']['meta']

            ## Course Language
            #print(course_url)
            collection_course_language= course_batches['overview'].get('language')

            ## Course requirements
            collection_course_requirements= course_batches['overview'].get('requirements')

            ## Course end Learning 
            collection_course_learning_in_course= course_batches['overview'].get('learn')

            ## Course Curriculum
            course_curriculum= {}
            course_curriculum_dict=course_batches['curriculum']
            for keys, values in course_curriculum_dict.items():
                #print(values)
                curriculum_title= values['title']
                curriculum_items= values['items']
                course_curriculum_topics=list()
                for tab_item_values in curriculum_items:
                    #print(tab_item_values['title'])
                    course_curriculum_topics.append(tab_item_values['title'])
                course_curriculum[curriculum_title]=course_curriculum_topics

            ## Course Pricing
            #collection_course_pricing= course_details['props']['pageProps']['data']['details']['pricing']

            if collection_course_mode=='live':
                ### live bathches has seperate tag with batches and id for that, we are converting batches to list
                #### then adding tag batch and pricing to get the details
                collection_course_pricing=list(course_details['props']['pageProps']['data']['batches'].values())[0]['batch'].get('pricing')
                
            else:
                collection_course_pricing= course_details['props']['pageProps']['data']['details'].get('pricing')
            #print(collection_course_pricing)

            ## Course instructors
            instructor_details={}
            instructors_list= course_batches['instructors']
            for instructor_id in instructors_list:
                #print(instructor_id)
                #print(course_details['props']['pageProps']['initialState']['init']['instructors'][instructor_id])
                instructor_details['id']=instructor_id
                instructor_details['email']=course_details['props']['pageProps']['initialState']['init']['instructors'][instructor_id].get('email')
                instructor_details['name']=course_details['props']['pageProps']['initialState']['init']['instructors'][instructor_id].get('name')
                instructor_details['description']=course_details['props']['pageProps']['initialState']['init']['instructors'][instructor_id].get('description')

            ## Course is job guarenteed
            collection_course_job_guarenteed= course_details['props']['pageProps']['data'].get('isJobGuaranteeProgram')


            ## Course features 
            collection_course_features= course_batches['overview'].get('features')
        except Exception as e:
            print("Error while parsing data")
            print("Error details:",e)
            logging.error("Exception raised: "+ str(e))
        ##Creating dictionary for course details row
        course_details_row={

            "Course_id":collection_course_id,
            "Course_category":course_category,
            "Course_title":collection_course_title,
            "Course_Url":course_url,
            "Course_description":collection_course_description,
            "Course_language":collection_course_language,
            "Course_requirements":collection_course_requirements,
            "Course_end_learning":collection_course_learning_in_course,
            "Course_pricing": collection_course_pricing,
            "Course_job_guarenteed":collection_course_job_guarenteed,
            "Course_mode":collection_course_mode,
            "Course_features":collection_course_features,
            "Course_instructor_details":instructor_details,
            "Course_curriculum": course_curriculum    
            }
        return course_details_row

    '''Create Database Connection'''
    def dbConnection(self):
        try:
            ##Db connection
            coursedb=self.dbclient[self.dbname]
            #print(self.dbclient.list_database_names())

            # Db droping older ones and creating collection
            course_cat_old= coursedb[self.dbcollectionname]
            course_cat_old.drop()
            course_cat= coursedb[self.dbcollectionname]
        except Exception as e:
            print("Could not able to connect to Database")
            print("Error details:",e)
            logging.error("Exception raised: "+ str(e))
        return course_cat

### Creating a function which runs all the data
## Getting all the course details
@app.route('/course_details', methods=['POST', 'GET'])
@cross_origin()
def run_course_details():

    #return "Hello"
    
    ### Getting All the Course Urls
    #driver_path="/opt/homebrew/bin/Chromedriver"
    ### Settings for Heroku
    browser_path = '/app/.apt/usr/bin/google_chrome'
    driver_path = '/app/.chromedriver/bin/chromedriver'
    try:
        ## Database client details
        dbclient= pymongo.MongoClient("mongodb+srv://mogodb:mongodb@cluster0.n86s3.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")
    except Exception as e:
        print("Custom Error: Mongodb Connection failed. please check the connection link")
        print("Error details:",e)
        logging.error("Exception raised: "+ str(e))
    #dbclient = client.test
    dbname='course_details'
    dbcollectionname='course_details_doc'
    ineuron_course_scrap=ineuron_Course(ineuron_url, dbclient, dbname, dbcollectionname)
    ineuron_course_scrap.getCourses(webdriver, browser_path, driver_path,sleep_time=2)
    logging.shutdown()
    return render_template('results.html')





if __name__=="__main__":
    app.run()