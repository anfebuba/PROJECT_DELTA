def numerosentre(a,b):
    for i in range(a+1,b,1):
        print(i)

n1=int(input('escriba el primero de dos números para mostrar los numeros que hay entre uno y otro: '))
n2= int(input('escriba el segundo de dos números para mostrar los numeros que hay entre uno y otro: '))


print('los numeros son: '), numerosentre(n1,n2)

