import json
import jsonschema as js
import os
import re
from dateutil.parser import parse
import pathlib
import src.Classes.config as config
import src.log as log


semanticPairDatePath = pathlib.Path("./src/Classes/semanticPairDate.txt")

# validate a data using a schema
def validate(data, profile):
    global errorPaths
    global existProperty
    global diffKeys

    # --------------------------------------------------------------------------
    # Set globals
    
    errorPaths = list()
    existProperty = list(data.keys())

    # --------------------------------------------------------------------------
    # Try to get schema from specified(?) profile 

    schema, schemaPath = None, None
    if profile is not None:
        schema, schemaPath = path_to_dict(pathlib.Path(profile))

    # --------------------------------------------------------------------------
    # Try to get schema from stored profile

    if schema is None:
        path = pathlib.Path(config.PROFILE_LOC)
        existProfile = os.listdir(path)
        predicate = get_predicate(data)
        profileName, profilePath, version = get_profile(data, path, existProfile)
        data = bioschemasPredicateRemoval(data, predicate)

        if profilePath != "":
            schema, profilePath = path_to_dict(profilePath)
            log.info(f"Validating against profile {profileName} {version}")
        elif profilePath == "":
            log.info(f"""The profile schemas, "{profileName}", does not yet exist in the profile JSON schema directory, please add it first by running buildprofile with the source data for "{profileName}".""")
            return -1

    # --------------------------------------------------------------------------
    # If schema has been found, attempt validation

    if schema is not None:
        # if the data uses only schemas.org properties, all property names should be lowerCamelCase
        if "@context" in data.keys() and type(data["@context"]) != list and "http://schema.org" in data["@context"]:
            schema["propertyNames"] = {"pattern": "^[a-z@\$][a-zA-Z]*$"}

        # ----------------------------------------------------------------------
        # Perform validation

        v = js.Draft7Validator(schema)
        errors = sorted(v.iter_errors(data), key=lambda e: e.path)

        # ----------------------------------------------------------------------
        # Process validation output

        log.info(f"=======================Validator Message:=================================")
        error_messages = []
        for e in errors:
            msg = ""
            # if property does not exist
            if "is a required property" in e.message:
                msg = f"{e.message} but it's missing."
            # if property exist but has error(s)
            else:
                if e.schema_path[0] == "properties":
                    del data[e.schema_path[1]]
                if "is not valid under any of the given schemas" in e.message:
                    msg = f"For property: {e.schema_path[1]}, {e.message}"
                elif "does not match" in e.message:
                    msg = f"Property name: {e.message}"
                else:
                    msg = e.message
                if "validityCheck" in e.schema.keys() :
                    log.info(e.schema["validityCheck"])
            log.error(msg)
            error_messages.append(msg)
            log.info(f"------")
            errorPaths.append(e.schema_path[len(e.schema_path)-1])

        diffKeys = set(list(existProperty)) - set(list(data.keys()))
        if len(errorPaths) == 0:
            log.info(f"The data is valid against this profile")
        elif len(errorPaths) > 0:
            diffKeys = set(list(existProperty)) - set(list(data.keys()))
            log.info(f"Existing property value(s) that has error: {*diffKeys,}")

        date_semantic_check(data)

        profilePathParts = list(profilePath.parts)
        listPath = pathlib.Path(config.PROFILE_MARG_LOC) / profilePathParts[-2] / profilePathParts[-1]
        listPath = listPath.with_suffix(config.PROFILE_MARG_EXT)

        if listPath.exists() is True:
            version = profilePath.name
            result = check_completeness(
                existProperty, diffKeys, listPath, profileName, version)
            result['Error Messages'] = error_messages
            return result
        return 0


def bioschemasPredicateRemoval(data, predicate):
    if type(data) is dict and "@type" in data.keys():
        for key, value in data.items():
            if type(value) is str and predicate in value:
                data[key] = value.replace(predicate, "")
            if type(value) is dict:
                bioschemasPredicateRemoval(value, predicate)
            if type(value) is list:
                for instance in value:
                    bioschemasPredicateRemoval(instance, predicate)
    return data


def profileVersionConform(value):
    valueType = type(value)
    profileName = ""
    version = ""
    url = ""
    if valueType is dict:
        for k, v in value.items():
            if type(v) is str and "bioschemas.org" in v:
                url = v
    elif valueType is list:
        for v in value:
            if type(v) is str and "bioschemas.org" in v:
                url = v
    elif valueType is str and "bioschemas.org" in value:
        url = value
    else:
        return "", -1

    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    if bool(re.match(regex, url)) is True:
        infoList = url.split("/")
        while "" in infoList:
            infoList.remove("")

#       the value is always a url link to the profile webpage on bioschemas which follows the same format
        profileName = infoList[3]
        version = infoList[4]
        return profileName, version

#         if the format of the string is not a url
    else:
        return "", -1


def create_marg_dict(profileName, version):
    result = dict()
    result["Profile Name"] = profileName
    result["Profile Version"] = version
    result["Minimum"] = dict()
    result["Recommended"] = dict()
    result["Optional"] = dict()
    return result


def update_completeness_dict(result, key1, key2, properties):
    result[key1][key2] = sorted(list(properties))
    return result


def check_completeness(existProperty, diffKeys, listPath, profileName, version):
    result = create_marg_dict(profileName, version)

    profileListDict = json.loads(listPath.read_text())
    # property name such as @type that are not in the Bioschemas profile but should be in the json ld therefore will not be count as extra properties
    with pathlib.Path(config.METADATA_DEFAULT_PROP).open() as f:
        metadataDefaultProp = f.read().splitlines()

    profileListDictValues = list(profileListDict.values())
    profileListDictValue = list()
    for v in profileListDictValues:
        profileListDictValue += v

    extraProp = (set(existProperty).difference(set(profileListDictValue))).difference(set(metadataDefaultProp))

    log.info(f"============Properties Marginality Report:============")

    for level in ['Minimum', 'Recommended', 'Optional']:
        valid = marginality_level_report(level_name = level,
                                         profile_list = profileListDict,
                                         existProperty = existProperty,
                                         diffKeys = diffKeys,
                                         result = result
                                         )
        if level == 'minimum':
            result['Valid'] = valid

    # Extra properties not included in the Bioschemas profile
    if len(list(extraProp)) == 0:
        log.info(f"\nThere is no property name in the metadata outside of the Bioschemas profile.")
    if len(list(extraProp)) != 0:
        log.info(f"\nThese properties names are in the metadata but not in the Bioschemas profile: {*extraProp,}")

    return result


def is_date(string, fuzzy=False):
    """
    Return whether the string can be interpreted as a date.

    :param string: str, string to check for date
    :param fuzzy: bool, ignore unknown tokens in string if True
    """
    try:
        parse(string, fuzzy=fuzzy)
        return True

    except ValueError:
        return False


# perform semantic check base on the relationship between property
def date_semantic_check(data):
    with semanticPairDatePath.open() as f:
        semanticPairDate = f.readlines()
        f.close()

    for line in semanticPairDate:
        pair = line.split()
        start = pair[0]
        end = pair[1]

        if start in data.keys() and is_date(data.get(start)) is False:
            log.info(f"""In property "{start}", "{data.get(start)}" has incorrect data format, months should be between 1 and 12, date should be between 1 and 31""")
        if end in data.keys() and is_date(data.get(end)) is False:
            log.info(f"""In property "{end}", "{data.get(end)}" has incorrect data format, months should be between 1 and 12, date should be between 1 and 31""")
#                as the date format check is done with the json schemas and incorrect property are removed
#                there is no point to check formate again
        if start in data.keys() and end in data.keys() and is_date(data.get(start)) and is_date(data.get(end)):
                staS = parse(data.get(start))
                endS = parse(data.get(end))
                if staS > endS:
                    log.info(f'''"{start}" : {data.get(start)} is after {end} : data.get(start), please double check.''')

    for key, value in data.items():
        if type(value) is dict:
            masterKeys = list()
            masterKeys.append(key)
            date_semantic_check_in_property(value, key, masterKeys)


# perform semantic check base on the relationship between property, inside other properties
def date_semantic_check_in_property(data, key, masterKeys):
    with semanticPairDatePath.open() as f:
        semanticPairDate = f.readlines()
        f.close()

    for line in semanticPairDate:
        pair = line.split()
        start = pair[0]
        end = pair[1]

#                as the date format check is done with the json schemas and incorrect property are removed
#                there is no point to check formate again
        if start in data.keys() and is_date(data.get(start)) is False:
            log.info(f"Inside property {masterKeys}, '{data.get(start)}' for property {start} has incorrect data format, months should be between 1 and 12, date should be between 1 and 31")
        if start in data.keys() and end in data.keys() and is_date(data.get(start)) and is_date(data.get(end)):
            log.info(f"Inside property {masterKeys}, '{data.get(end)}' for property {end} has incorrect data format, months should be between 1 and 12, date should be between 1 and 31")
            staS = parse(data.get(start))
            endS = parse(data.get(end))
            if staS > endS:
                log.info(f"Inside property {masterKeys} '{start}' : {data.get(start)} is after '{end}' : {data.get(start)}, please double check.")
    for key, value in data.items():
        if type(value) is dict:
#                 masterKey = ke
            masterKeys.append(key)
            date_semantic_check_in_property(value, key, masterKeys)

            
# loads the string from the file to a json object
def path_to_dict(path):
    path = pathlib.Path(path)
    orgString = path.read_text()
    newDict = json.loads(orgString,
                            object_pairs_hook=dict_raise_on_duplicates)
    return newDict, path


def str_to_dict(orgString):
    newDict = json.loads(orgString,
                            object_pairs_hook=dict_raise_on_duplicates)
    return newDict


# supply method used to reject duplicate keys
def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    schemaOrg = False
    for k, v in ordered_pairs:
        if re.search(r"\s", k):
            log.info(f"Please remove the whitespace(s) in property name {k} the Validator will proceed without the whitespace(s)\n")
            k = k.strip()
        if re.search("[^a-zA-Z@\$]", k) != None and "conformsTo" not in k:
            log.info(f"Please be noted there are non alphabetic character in property name {k} schema.org has no property name with non alphabetic character therefore the Bioschemas validator will not validate this property.")
        if k in d:
            log.info(f"Duplicate property: {k} the value for the last %r will be used {k}")
        elif type(v) is dict:
            masterKeys = list()
            masterKeys.append(k)
            d[k] = dict_raise_on_duplicates_recursive(v, masterKeys)
        else:
            d[k] = v
    return d


def dict_raise_on_duplicates_recursive(ordered_pairs, masterKeys):
    """Reject duplicate keys."""
    d = {}

    for k, v in ordered_pairs.items():
        if re.search(r"\s", k) != None:
            log.info(masterKeys)
        if re.search("[^a-zA-Z@\$]", k) != None:
            log.info(masterkeys)
        if k in d:
            log.info(masterkeys)
        elif type(v) is dict:
            masterKeys.append(k)
            d[k] = dict_raise_on_duplicates_recursive(v, masterKeys)
        else:
            d[k] = v
    return d


def hasNumbers(inputString):
    return bool(re.search(r'\d', inputString))


def sortby(x):
    try:
        if x.split(".")[0] == "0":
            x = x[x.index(".")+1:x.index("-")]
        else:
            x = x[:x.index(".")] + x[x.index("."):x.index("-")]
        return float(x)
    except ValueError:
        return float('inf')


def marginality_level_report(level_name    = '',
                             profile_list  = None,
                             existProperty = None,
                             diffKeys      = None,
                             result        = None
                             ):
    log.info(f"Marginality: {level_name}")
    key_name = level_name.lower()

    number     = len(profile_list[key_name])
    exist      = set(profile_list[key_name]).intersection(existProperty)
    error      = set(profile_list[key_name]).intersection(diffKeys)
    difference = set(profile_list[key_name]) - set(existProperty)

    if number == 0:
        log.info(f"\tThere are no minimum property required by this profile.")
        update_completeness_dict(result, level_name, "Missing", "")
        update_completeness_dict(result, level_name, "Implemented", "")
        update_completeness_dict(result, level_name, "Error", "")
    else:
        if len(list(difference)) != 0:
            log.error(f"\tRequired property that are missing: {*difference,}")
        else:
            log.info(f"\tThe data has all the required property(ies).")

        if len(error) != 0:
            log.error(f"\tRequired property that has error: {*error,}")
        else:
            log.success(f"\tImplemented required property has no error.")

        update_completeness_dict(result, level_name, "Missing", difference)
        update_completeness_dict(result, level_name, "Implemented", exist)
        update_completeness_dict(result, level_name, "Error", error)

    result["Valid"] = "True" if len(difference) == 0 and len(error) == 0 else "False"


def get_predicate(data):
    predicate = ""
    if "@context" in data.keys():
        if type(data["@context"]) is list:
            for item in data["@context"]:
                if type(item) is dict:
                    for key, value in item.items():
                        if "http://bioschemas.org/" in value or "https://bioschemas.org/" in value:
                            predicate = key + ":"
    return predicate

def get_profile(data, path, existProfile):
    profileName = ""
    profilePath = ""
    version = ""

    # find the profile the data conforms to
    if "http://purl.org/dc/terms/conformsTo" in data.keys():
        profileName, version = profileVersionConform(data["http://purl.org/dc/terms/conformsTo"])
        # if the property value has a profile version
        if version != -1:
            profilePath = pathlib.Path(config.PROFILE_LOC) / profileName / (version + config.PROFILE_EXT)
            #if the path the data conform does not exist, erase the profilePath value
            if profilePath.exists() is False:
                log.warn(f"The profile the data claims to conform to, {profilePath}, is does not exist. Therefore the most recently release or draft version of the same type will be used to validate the data instead.")
                profilePath = ""
    # if there is no conformTo, see the metadata type
    elif "@type" in data.keys():
        if type(data["@type"]) is str:
            profileName = data["@type"]
        elif type(data["@type"]) is list:
            for t in data["@type"]:
                if t in existProfile:
                    profileName = t
            # if none of the type in the array is a Bioschemas profile
            if profileName == "":
                log.info(f"This metadata is of type: {data['@type']}, none is an existing Bioschemas profile type.")
                return

    if profilePath == "":
        profilePath = get_fallback_profile_path(profileName, path, existProfile)

    return (profileName, profilePath, version)


def get_fallback_profile_path(profileName, path, existProfile):
    # if the data did not have a profile link it conform to, only the type
    if profileName in existProfile:
        pathWithProfileName = path / profileName
        if pathWithProfileName.is_dir():
            listv = os.listdir(pathWithProfileName)
            listv.sort(key=sortby, reverse=True)
            releaseList = [item for item in listv if "RELEASE" in item]
            if releaseList != []:
                version = releaseList[0]
            else:
                version = listv[0]
        profilePath = pathlib.Path(config.PROFILE_LOC, profileName, version)

    return profilePath
