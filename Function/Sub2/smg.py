print("Hello SAMSUNG")

def d2b(num,l=[]):
    if(num>=1):
        d2b(num//2,l)
        l.append(num%2)
    #print(num%2, end=" ")
    l=[str(i) for i in l]
    return "".join(l)


def get_num(l,k=5,p=2):
    end=len(l)-p
    start=end-k+1
    print(start)
    if(start>=0):
        print("==Binary is ",l)
        print("==Extracted from pos %s is %s"% (p,l[start:end+1]))
        res=l[start:end+1]
        return int(res,2)
    else:
        print("K value exceeds the digits from the given p")
    
out=d2b(171)
print(out)
print(get_num(out))



def braces(inp):
    l='{(['
    r='})]'
    res=[]
    d={']':'[',')':'(','}':'{'}
    for i in inp:
        if i in l:
            res.append(i)
        elif i in r:
            if(len(res)!=0):
                if(res[-1]==d[i]):
                    res.pop()
                else:
                    return False
            else:
                return False
    return len(res)==0
    
    
print(braces('{{()}}'))


def pattern(inp):
    for i in range(inp):
        print('*' * i)
        
    
pattern(5)

def rec_fibo(num,d={0:0,1:1}):
    if(num in d):
        return d[num]
    else:
        d[num] = rec_fibo(num-1) + rec_fibo(num-2)
        return d[num]

for i in range(7):
    print(rec_fibo(i))
    
    
    
    

class bank:
    
    def __init__(self):
        self.bal = 0
        
    
    def debit(self,amt):
        if(self.bal>amt):
            self.bal = self.bal - amt
        else:
            print("Insufficient Balance: %s"%(self.bal))
            
            
    def credit(self,amt):
        self.bal = self.bal + amt


    def balance(self):
        print("Balance: %s "%self.bal)
        
    def main(self):
        while(True):
            inp = int(input("Enter an option\n 1.Debit\n 2.Credit\n 3.BalanceEnquiry\n 4.Exit\n: "))
            d={1:'debit',2:'credit',3:'balance'}
            if(inp  == 1):
                amt = int(input('Enter the amt to debit: '))
                self.debit(amt)
            elif(inp == 2):
                amt=int(input('Enter the amt to credit: '))
                self.credit(amt)
            elif(inp == 3):
                self.balance()
                
            else:
                exit()
if __name__ == '__main__':
    b = bank()
    b.main()
            
        