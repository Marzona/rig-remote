python setup.py test
python setup.py develop  && python setup.py sdist && python setup.py bdist_egg 
echo "egg generated. ready to upload?"

read a

python setup.py sdist upload
