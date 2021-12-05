import json
import sys
import requests
import shapefile
from fastkml import kml

def mainFunc():
    if len(sys.argv) < 6 or len(sys.argv) > 7:
        print("Automatically gets all house listings in the bounding box of the supplied kml file from Realtor.ca and creates a shapefile of those listings")
        print("usage:")
        print("KML File path arg 1")
        print("cookie str arg 2")
        print("output file name arg 3")
        print("houses only arg 4")
        print("detached only arg 5")
        print("acres in arg 6 (optional)")
        return
    fileStr = sys.argv[1]
    cookieStr = sys.argv[2]
    outputFileName = sys.argv[3]
    housesOnly = sys.argv[4] == 'true'
    detachedOnly = sys.argv[5] == 'true'
    useMinacres = False
    if (len(sys.argv) == 7):
        useMinacres = True
        minAcres = sys.argv[6]
    
    file = open(fileStr, "r")
    kmlDoc = file.read()
    kmlBytes = bytes(bytearray(kmlDoc, encoding='utf-8'))
    kmlObj = kml.KML()
    kmlObj.from_string(kmlBytes)
    features = list(kmlObj.features())
    placemarkList = list(features[0].features())
    bounds = placemarkList[0].geometry.bounds
    latMin = str(bounds[1])
    latMax = str(bounds[3])
    lonMin = str(bounds[0])
    lonMax = str(bounds[2])
    file.close()

    
    url = "https://api2.realtor.ca/Listing.svc/PropertySearch_Post"
    pageSize = 200

    headersDict = {
        'referer': 'https://www.realtor.ca/',
        'cookie': cookieStr
    }
    currentPage = 1
    dataObj = {
        'LatitudeMax': latMax,
        'LongitudeMax': lonMax,
        'LatitudeMin': latMin,
        'LongitudeMin': lonMin,
        'Sort':'6-D',
        'PropertyTypeGroupID':'1',
        'PropertySearchTypeId':'1',
        'TransactionTypeId':'2',
        'Currency':'CAD',
        'RecordsPerPage':'12',
        'ApplicationId':'1',
        'CultureId':'1',
        'CurrentPage':str(currentPage)
    }
    if (housesOnly):
        dataObj["BuildingTypeId"] = '1'
    if (detachedOnly):
        dataObj["ConstructionStyleId"] = '3'
    if (useMinacres):
        dataObj["LandSizeRange"] = minAcres + '-0'

    r = requests.post(url,headers=headersDict, data=dataObj)
    if r.status_code == requests.codes.ok:
        totalResults = r.json()["Paging"]["TotalRecords"]
        remainder = totalResults % pageSize
        pages = int(totalResults/pageSize) if remainder == 0 else int(totalResults/pageSize)+1
        dataObj["RecordsPerPage"] = str(pageSize)
        print("there are "+str(totalResults)+" results, and "+str(pages)+" pages of up to "+str(pageSize)+" records")
    else:
        print("getting the number of records went wrong. exiting")
        return
    
    shpWriter = shapefile.Writer(outputFileName)
    shpWriter.field('price', 'N', decimal=2)
    shpWriter.field('address', 'C', size=255)
    shpWriter.field('landSize', 'C', size=100)
    shpWriter.field('bedrooms', 'C', size=50)
    shpWriter.field('buildingSize', 'C', size=100)
    shpWriter.field('url', 'C', size=255)
    shpWriter.field('picture', 'C', size=255)
    shpWriter.field('googleMaps', 'C', size=255)
    shpWriter.field('html', 'C', size=255)

    addedFeatures = 0
    while currentPage <= pages:
        addedFeatures += getOnePage(url, headersDict, dataObj, shpWriter, currentPage)
        currentPage += 1
        dataObj["CurrentPage"] = str(currentPage)
    
    shpWriter.close()
    
    prj = open(outputFileName+".prj", "w")
    epsg = 'GEOGCS["WGS 84",'
    epsg += 'DATUM["WGS_1984",'
    epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
    epsg += ',PRIMEM["Greenwich",0],'
    epsg += 'UNIT["degree",0.0174532925199433]]'
    prj.write(epsg)
    prj.close()

    print("total results: " + str(totalResults))
    print("added features: " + str(addedFeatures))

def getOnePage(pUrl, pHeaders, pData, pShpWriter, pCurrentPage):
    addedFeatures = 0
    print("getting page " + str(pCurrentPage))
    r = requests.post(pUrl,headers=pHeaders,data=pData)

    if r.status_code == requests.codes.ok:
        realtorPrefix = "https://www.realtor.ca"
        blankPicture = "https://static.vecteezy.com/system/resources/previews/002/077/027/original/house-icon-sign-free-vector.jpg"

        jsonResult = r.json()
        print(str(jsonResult["ErrorCode"]))
        for result in jsonResult["Results"]:
            #Price
            price = result["Property"]["PriceUnformattedValue"]
            
            #Location
            addressObj = result["Property"]["Address"]
            latitude = addressObj["Latitude"]
            longitude = addressObj["Longitude"]
            address = addressObj["AddressText"]
            
            #Land
            landSizeObj = result["Land"]
            landSize = landSizeObj["SizeTotal"] if "SizeTotal" in landSizeObj else "noLandSize"
            
            #Building info
            buildingObj = result["Building"]
            bedrooms = buildingObj["Bedrooms"] if "Bedrooms" in buildingObj else "noBedrooms"
            buildingSize = buildingObj["SizeInterior"]  if "SizeInterior" in buildingObj else "noSize"
            
            #URLs
            url = realtorPrefix+result["RelativeURLEn"]
            picture = result["Property"]["Photo"][0]["LowResPath"] if "Photo" in result["Property"] else blankPicture
            googleMaps = "https://www.google.com/maps/@"+latitude+","+longitude+",1000m/data=!3m1!1e3"
            html = '<a href="'+url+'"><img src="'+picture+'" width="50" height="50"></a>' if "Photo" in result["Property"] else '<a href='+url+'>'
            
            pShpWriter.point(float(longitude), float(latitude))
            pShpWriter.record(price, address, landSize, bedrooms, buildingSize, url, picture, googleMaps, html)
            addedFeatures += 1
            print("\tadding " + str(address))
    else:
        print("not good response: " + str(r.status_code) + "page: " + pCurrentPage)

    return addedFeatures

if __name__ == '__main__':
    mainFunc()
