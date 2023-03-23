print_result()
{
    if [[ $1 == $2 ]]; then
        echo Done!
    else
        echo FAIL!
        exit 1
    fi
}

# test if i2cdetect is available (check if i2c-tools are properly installed)

IFS='\n'
echo $(i2cdetect -l)
print_result $? 0

# test if device i2c-0 works correctly

# Write value 0x42 to to register 0x11 of the i2C device 
# connected to i2c-0 bus at address 0x1C
i2cset -y 0 0x1C 0x11 0x42
print_result $(i2cget -y 0 0x1C 0x11) 0x42

# Write value 0x43 to to register 0x00 of the i2C device 
# connected to i2c-0 bus at address 0x1C
i2cset -y 0 0x1C 0x00 0x43
print_result $(i2cget -y 0 0x1C 0x00) 0x43
